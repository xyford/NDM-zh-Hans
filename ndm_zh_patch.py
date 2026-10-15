# -*- coding: utf-8 -*-
"""
Neat Download Manager 汉化补丁器 (可重复执行, 支持 NDM 更新后重跑)

原理:
  1. 按"内容"在 exe 中定位英文 UI 字符串(UTF-16LE), 不依赖固定偏移 -> 更新后仍可用
  2. 在代码/数据节中找到所有指向这些字符串的 32 位绝对地址引用
  3. 把中文译文写入新增的 .l10n 节, 引用改为指向译文 (原字符串保留不动, 间接引用不受影响)
  4. 对"长度前缀"用法 (push len; push ptr) 同步修补长度操作数

用法:
  python ndm_zh_patch.py <NeatDM.exe 路径> [--dry-run] [--quiet]
退出码: 0=成功或已汉化  1=失败  2=已是汉化版(无需操作)
"""
import sys, os, json, struct, shutil, argparse

IB_DEFAULT = 0x400000

def parse_pe(data):
    if data[:2] != b'MZ':
        raise ValueError('not a PE file')
    peoff = struct.unpack('<I', data[0x3c:0x40])[0]
    if data[peoff:peoff+4] != b'PE\0\0':
        raise ValueError('bad PE signature')
    nsec = struct.unpack('<H', data[peoff+6:peoff+8])[0]
    opt_size = struct.unpack('<H', data[peoff+20:peoff+22])[0]
    opt = peoff + 24
    magic = struct.unpack('<H', data[opt:opt+2])[0]
    if magic != 0x10b:
        raise ValueError('not PE32 (only 32-bit supported)')
    imagebase = struct.unpack('<I', data[opt+28:opt+32])[0]
    sec_align = struct.unpack('<I', data[opt+32:opt+36])[0]
    file_align = struct.unpack('<I', data[opt+36:opt+40])[0]
    size_image = struct.unpack('<I', data[opt+56:opt+60])[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        o = sec_off + i*40
        name = data[o:o+8].rstrip(b'\0').decode('ascii', 'replace')
        vs, va, rs, rp = struct.unpack('<IIII', data[o+8:o+24])
        sections.append({'name': name, 'vs': vs, 'va': va, 'rs': rs, 'rp': rp, 'hdr_off': o})
    return {'peoff': peoff, 'opt': opt, 'nsec': nsec, 'sec_off': sec_off,
            'imagebase': imagebase, 'sec_align': sec_align, 'file_align': file_align,
            'size_image': size_image, 'sections': sections}

def off2va(pe, off):
    for s in pe['sections']:
        if s['rp'] <= off < s['rp'] + max(s['rs'], s['vs']):
            return s['va'] + (off - s['rp'])
    return None

def find_ref_sites(data, va_abs):
    """全文件搜索 4 字节绝对地址引用, 返回文件偏移列表"""
    needle = struct.pack('<I', va_abs)
    out = []
    pos = 0
    while True:
        i = data.find(needle, pos)
        if i < 0:
            break
        out.append(i)
        pos = i + 1
    return out

def reloc_rvas(pe, data):
    """解析 .reloc, 返回所有 HIGHLOW 重定位项的 RVA 集合
    (这些位置在链接时被确认为绝对地址 —— 只修补集合内位置可彻底避免误伤数值常量,
      且保证 ASLR 重定位后指针仍指向 .l10n 译文)"""
    ddir = pe['opt'] + 96
    r_rva, r_sz = struct.unpack('<II', data[ddir+5*8:ddir+5*8+8])
    out = set()
    if not r_rva:
        return out
    def r2o(rva):
        for s in pe['sections']:
            if s['va'] <= rva < s['va'] + max(s['vs'], s['rs']):
                return s['rp'] + (rva - s['va'])
        return None
    off = r2o(r_rva)
    end = off + r_sz
    while off + 8 <= end:
        page_rva, blk_sz = struct.unpack('<II', data[off:off+8])
        if blk_sz < 8:
            break
        n = (blk_sz - 8) // 2
        for j in range(n):
            e = struct.unpack('<H', data[off+8+j*2:off+10+j*2])[0]
            if (e >> 12) == 3:  # IMAGE_REL_BASED_HIGHLOW
                out.add(page_rva + (e & 0xfff))
        off += blk_sz
    return out

def is_patched(path):
    """检测目标 exe 是否已汉化 (存在 .l10n 节)"""
    try:
        data = open(path, 'rb').read()
        pe = parse_pe(data)
        return any(s['name'] == '.l10n' for s in pe['sections'])
    except Exception:
        return False

def make_len_detector():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    def analyze(code_bytes, code_va, site_off, str_len):
        """site_off = 引用 imm32 在 code_bytes 内的偏移. 返回 len_site 或 None.
        判定 (ptr,len) 构造的规则:
          1. 在所有能精确汇合到 site 的反汇编路径中取引用前指令最多的一条(最可信);
          2. 从引用指令向前找最近的 push imm —— 若 imm==strlen 且它与引用之间
             没有其它 push (只允许 xor/mov [mem]/lea 等初始化指令), 判定为长度操作数。
          布局参数(如 push 0x12 高度值)与引用之间隔着其它 push, 会被自动排除。"""
        best = None
        for start_delta in range(2, 31):
            start = site_off - start_delta
            if start < 0:
                break
            try:
                insns = list(md.disasm(code_bytes[start:site_off+8], code_va + start))
            except Exception:
                continue
            ref_idx = None
            for idx, ins in enumerate(insns):
                a = ins.address
                if a <= code_va + site_off < a + ins.size:
                    if ins.imm_size and (a + ins.imm_offset) == code_va + site_off:
                        ref_idx = idx
                    break
                if a > code_va + site_off:
                    break
            if ref_idx is None or ref_idx < 3:
                continue
            if best is None or ref_idx > best[0]:
                best = (ref_idx, insns)
        if best is None:
            return None
        ref_idx, insns = best
        # 向前找最近的 push imm
        for k in range(ref_idx - 1, -1, -1):
            if ref_idx - k > 9:
                break
            ins = insns[k]
            if ins.mnemonic == 'push' and ins.operands and ins.operands[0].type == CS_OP_IMM:
                if ins.operands[0].imm == str_len and ins.imm_size in (1, 4):
                    return ((ins.address - code_va) + ins.imm_offset, ins.imm_size)
                return None  # 最近的 push 不是串长 -> 非 (ptr,len) 用法
            if ins.mnemonic in ('call', 'jmp', 'ret'):
                return None  # 跨越基本块边界, 放弃
        return None

    return analyze

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe', help='NeatDM.exe 路径')
    ap.add_argument('--translations', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations.json'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    exe = os.path.abspath(args.exe)
    data = open(exe, 'rb').read()
    pe = parse_pe(data)
    IB = pe['imagebase']

    if any(s['name'] == '.l10n' for s in pe['sections']):
        print('[=] 已是汉化版 (存在 .l10n 节), 无需操作')
        return 2

    translations = json.load(open(args.translations, encoding='utf-8'))
    detect_len = make_len_detector()
    relocs = reloc_rvas(pe, data)
    if not args.quiet:
        print(f'[*] 重定位项 {len(relocs)} 个')

    text = next(s for s in pe['sections'] if s['name'] == '.text')
    text_bytes = data[text['rp']:text['rp']+text['rs']]

    # 收集所有被引用过的 VA (用于子串重叠检查)
    # (跳过全量扫描, 仅对本表条目检查)

    plan = []   # (old_va, zh, ref_sites[file_off], len_sites[(file_off,size)], en)
    problems = []
    for ent in translations:
        en, zh = ent['en'], ent['zh']
        needle = en.encode('utf-16le')
        # 找所有出现位置 (要求串尾是 00 00)
        occ = []
        pos = 0
        while True:
            i = data.find(needle, pos)
            if i < 0:
                break
            if data[i+len(needle):i+len(needle)+2] == b'\0\0':
                va = off2va(pe, i)
                if va is not None:
                    occ.append((i, va))
            pos = i + 1
        if not occ:
            problems.append(f'[!] 未找到(新版可能改了文案): {en[:60]!r}')
            continue
        en_wlen = len(en)  # WCHAR 数
        zh_wlen = len(zh)
        for off, va in occ:
            refs = find_ref_sites(data, IB + va)
            # 引用不应落在 .l10n 预留区(尚未添加) 之外无限制; 排除引用恰好落在该字符串自身数据内的巧合
            refs = [r for r in refs if not (off <= r < off + len(needle))]
            # 只保留有 HIGHLOW 重定位项的位置 (链接器确认的绝对地址), 杜绝误伤数值常量
            n_all = len(refs)
            refs = [r for r in refs if off2va(pe, r) in relocs]
            if not refs:
                if n_all:
                    problems.append(f'[!] 引用无重定位项(疑数值巧合), 跳过: {en[:60]!r} @VA {va:x}')
                else:
                    problems.append(f'[!] 无引用, 跳过: {en[:60]!r} @VA {va:x}')
                continue
            # 长度前缀检测 (仅 .text 内的引用): (ptr,len) 构造判定见 make_len_detector
            len_sites = []
            for r in refs:
                if text['rp'] <= r < text['rp'] + text['rs']:
                    site = detect_len(text_bytes, text['va'], r - text['rp'], en_wlen)
                    if site is not None:
                        len_sites.append((text['rp'] + site[0], site[1]))
            if len_sites and zh_wlen > 127:
                problems.append(f'[!] 译文过长(>127)且存在长度前缀引用, 跳过: {en[:40]!r}')
                continue
            plan.append((va, zh, refs, len_sites, en))

    if not args.quiet:
        print(f'[*] 计划修补 {len(plan)} 处字符串, 警告 {len(problems)} 条')
        for p in problems:
            print(p)

    # 重叠检查: 任一被引用 VA 落在另一待译串内部 -> 报警
    vas = sorted(p[0] for p in plan)
    for va, zh, refs, ls, en in plan:
        end = va + len(en)*2
        for other in vas:
            if va < other < end:
                problems.append(f'[!] 子串重叠: VA {other:x} 在 {en[:40]!r} 内部')

    if args.dry_run:
        print('[dry-run] 不写出文件')
        return 0

    # ==== 构建 .l10n 节 ====
    l10n = bytearray()
    new_va_of = {}  # old_va -> new_va (绝对 VA, 含 imagebase)
    for va, zh, refs, ls, en in plan:
        if len(l10n) % 2:
            l10n += b'\0'
        new_va_of[va] = len(l10n)  # 暂存节内偏移
        l10n += zh.encode('utf-16le') + b'\0\0'

    last = max(pe['sections'], key=lambda s: s['va'] + s['vs'])
    new_sec_va = (last['va'] + max(last['vs'], last['rs']) + pe['sec_align'] - 1) // pe['sec_align'] * pe['sec_align']
    fa = pe['file_align']
    new_raw = (len(data) + fa - 1) // fa * fa
    new_rs = (len(l10n) + fa - 1) // fa * fa

    # 节表空间检查
    sec_table_end = pe['sec_off'] + pe['nsec'] * 40
    first_raw = min(s['rp'] for s in pe['sections'] if s['rs'] > 0)
    if sec_table_end + 40 > first_raw:
        print('[X] 节表无空位, 无法添加 .l10n 节')
        return 1

    out = bytearray(data)
    # 补齐到新节原始偏移
    if len(out) < new_raw:
        out += b'\0' * (new_raw - len(out))
    # 写入节头
    hdr = sec_table_end
    out[hdr:hdr+8] = b'.l10n\0\0\0'
    struct.pack_into('<I', out, hdr+8, len(l10n))          # VirtualSize
    struct.pack_into('<I', out, hdr+12, new_sec_va)        # VirtualAddress
    struct.pack_into('<I', out, hdr+16, new_rs)            # SizeOfRawData
    struct.pack_into('<I', out, hdr+20, new_raw)           # PointerToRawData
    struct.pack_into('<II', out, hdr+24, 0, 0)             # reloc/lineno
    struct.pack_into('<HH', out, hdr+32, 0, 0)
    struct.pack_into('<I', out, hdr+36, 0x40000040)        # initialized data | read
    # NumberOfSections / SizeOfImage
    struct.pack_into('<H', out, pe['peoff']+6, pe['nsec']+1)
    new_size_image = (new_sec_va + len(l10n) + pe['sec_align'] - 1) // pe['sec_align'] * pe['sec_align']
    struct.pack_into('<I', out, pe['opt']+56, new_size_image)

    # 计算新 VA 并写入节数据
    abs_new = {}
    for va, zh, refs, ls, en in plan:
        abs_new[va] = IB + new_sec_va + new_va_of[va]
    out += l10n
    out += b'\0' * (new_raw + new_rs - len(out))

    # ==== 修补引用 (在原文件长度范围内, 避开 .l10n 新区) ====
    patched_refs = 0
    for va, zh, refs, ls, en in plan:
        nv = struct.pack('<I', abs_new[va])
        ov = struct.pack('<I', IB + va)
        for r in refs:
            if out[r:r+4] == ov:
                out[r:r+4] = nv
                patched_refs += 1
    # ==== 修补长度操作数 ====
    patched_lens = 0
    for va, zh, refs, ls, en in plan:
        for off, size in ls:
            if size == 1:
                cur = out[off]
                if cur == len(en):
                    out[off] = len(zh)
                    patched_lens += 1
            else:
                cur = struct.unpack('<I', out[off:off+4])[0]
                if cur == len(en):
                    struct.pack_into('<I', out, off, len(zh))
                    patched_lens += 1

    tmp = exe + '.l10n_tmp'
    open(tmp, 'wb').write(bytes(out))
    os.replace(tmp, exe)
    print(f'[OK] 已汉化: {len(plan)} 个字符串, {patched_refs} 处引用, {patched_lens} 处长度操作数')
    if problems:
        print(f'[*] 其中 {len(problems)} 条提示(多为新版文案变动或间接引用, 不影响主界面)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
