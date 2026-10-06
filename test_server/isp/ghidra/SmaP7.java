// P7 线4: SMA(0x94000000) 访问者 + EP 寄存器写入点 + 常量指纹
// 动机: p7 = Cortex-A9 OS 镜像(0xc09 已实机验证)。
//   若 ISP 配方经 SMA 共享内存传递，则 Linux 侧也能写 ⇒ 无需改固件。
//   另一路: EP 寄存器物理基址 0x2082xxxx 的写入点。
//@category NX-KS2
//@author NX-KS2

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import java.io.*;
import java.util.*;

public class SmaP7 extends GhidraScript {

    private File dir;
    private DecompInterface di;
    private Map<String, String> cache = new HashMap<>();

    // 实机实测的地址
    private static final long SMA_BASE   = 0x94000000L;
    private static final long SMA_SIZE   = 0x09000000L;
    private static final long EP_TOP     = 0x20820000L;
    private static final long EP_NOG     = 0x20821c00L;
    private static final long EP_3DLUT   = 0x2082b000L;
    private static final long RAM_BASE   = 0x81000000L;   // p7 的运行时数据区

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();
        di = new DecompInterface();
        di.openProgram(currentProgram);

        a_smaAccess();
        b_epAccess();
        c_floatTables();
        d_dataSegScan();

        di.dispose();
        println("SmaP7 done.");
    }

    // ==== A: 谁引用 SMA 基址 ====
    private void a_smaAccess() throws Exception {
        PrintWriter p = pw("30_sma_access.txt");
        p.println("=== A: SMA 0x" + Long.toHexString(SMA_BASE) + " 的访问者 ===");
        p.println("（此前裸镜像扫描 936 处命中被证明全是噪声，这次有 Ghidra 引用图）");

        // A1. Ghidra 已定义的标量里有没有等于 SMA_BASE 的
        p.println("\n--- A1: 值为 SMA_BASE 的已定义标量 ---");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int n = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getLength() != 4) continue;
            Object v = d.getValue();
            if (!(v instanceof Number)) continue;
            long val = ((Number) v).longValue() & 0xFFFFFFFFL;
            if (val == SMA_BASE || val == (SMA_BASE & 0xFFFFFFFFL)) {
                List<String> r = refsTo(d.getAddress());
                p.printf("  %s = 0x%x  refs=%d %s%n", d.getAddress(), val, r.size(), r);
                if (++n > 30) break;
            }
        }
        p.println("  found = " + n);

        // A2. 落在 SMA 区间内的所有标量（可能是段基址/偏移表）
        p.println("\n--- A2: 值落在 SMA 区间 [0x94000000,0x9d000000) 的标量 ---");
        it = currentProgram.getListing().getDefinedData(true);
        Map<String, Integer> hist = new TreeMap<>();
        List<String> lines = new ArrayList<>();
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getLength() != 4) continue;
            Object v = d.getValue();
            if (!(v instanceof Number)) continue;
            long val = ((Number) v).longValue() & 0xFFFFFFFFL;
            if (val >= SMA_BASE && val < SMA_BASE + SMA_SIZE) {
                List<String> r = refsTo(d.getAddress());
                lines.add(String.format("  %s = 0x%08x  refs=%d %s", d.getAddress(), val, r.size(), r));
                if (lines.size() <= 40) hist.merge("in", 1, Integer::sum);
            }
        }
        for (String s : lines) p.println(s);
        p.println("  total = " + lines.size());

        // A3. 指令流里搜立即数 0x94000000（ARM MOVW/MOVT / LDR 字面量）
        p.println("\n--- A3: LDR 字面量池里的 0x94xxxxxx ---");
        int lit = 0;
        for (Reference r : allRefs()) {
            if (r.getReferenceType().isData()) {
                Address to = r.getToAddress();
                if (to.getOffset() >= SMA_BASE && to.getOffset() < SMA_BASE + SMA_SIZE) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    if (lit < 40) p.printf("  %s -> %s  %s%n", r.getFromAddress(),
                            to, f == null ? "(no func)" : f.getName());
                    lit++;
                }
            }
        }
        p.println("  data refs into SMA window = " + lit);

        // A4. 之前记录的内存段表 0x9fc0 —— 谁引用它?
        p.println("\n--- A4: 内存段表 @0x9fc0（此前发现 SMA 基址在此）---");
        for (long a = 0x9fc0; a < 0xa040; a += 4) {
            List<String> r = refsTo(toAddr(a));
            if (!r.isEmpty()) p.printf("  0x%x  %s  refs=%d %s%n", a, scalarStr(a), r.size(), r);
        }
        p.close();
    }

    // ==== B: EP 物理基址写入点 ====
    private void b_epAccess() throws Exception {
        PrintWriter p = pw("31_ep_access.txt");
        p.println("=== B: EP 寄存器物理基址的引用 ===");
        long[] eps = {EP_TOP, EP_NOG, EP_3DLUT, 0x20823000L, 0x2082a000L};
        for (long e : eps) {
            p.println("\n--- 0x" + Long.toHexString(e) + " ---");
            int n = 0;
            DataIterator it = currentProgram.getListing().getDefinedData(true);
            while (it.hasNext()) {
                Data d = it.next();
                if (d.getLength() != 4) continue;
                Object v = d.getValue();
                if (!(v instanceof Number)) continue;
                if ((((Number) v).longValue() & 0xFFFFFFFFL) != e) continue;
                List<String> r = refsTo(d.getAddress());
                p.printf("  scalar @ %s  refs=%d %s%n", d.getAddress(), r.size(), r);
                n++;
                if (n > 10) break;
            }
            if (n == 0) p.println("  (镜像里没有这个常量)");
        }
        p.close();
    }

    // ==== C: 常量指纹 —— 找浮点表(3x3 矩阵 / 44 锚点曲线) ====
    private void c_floatTables() throws Exception {
        PrintWriter p = pw("32_float_tables.txt");
        p.println("=== C: 浮点表指纹搜索（gamma 3x3 矩阵 / 44 锚点曲线）===");
        Memory mem = currentProgram.getMemory();

        // C1. 连续 9 个"合理浮点"(0<=|v|<=4, 且非 NaN/Inf)
        p.println("\n--- C1: 连续 9 个合理浮点（3x3 矩阵候选）---");
        byte[] img = readImage();
        List<long[]> m9 = findFloatRuns(img, 9, 4.0);
        p.println("  候选数 = " + m9.size() + " (显示前 30)");
        for (int i = 0; i < Math.min(30, m9.size()); i++) {
            long[] r = m9.get(i);
            p.printf("  0x%x: [%s] refs=%d %s%n", r[0], floats(img, r[0], 9, "%.4f"), refsTo(toAddr(r[0])).size(),
                    refsTo(toAddr(r[0])));
        }

        // C2. 连续 22 个（锚点曲线的一半）
        p.println("\n--- C2: 连续 22 个 [0,1] 浮点（gamma 锚点候选，值域应是 0..1）---");
        List<Long> m22 = findUnitRuns(img, 22);
        p.println("  候选数 = " + m22.size() + " (显示前 20)");
        for (int i = 0; i < Math.min(20, m22.size()); i++) {
            long off = m22.get(i);
            StringBuilder sb = new StringBuilder();
            for (int k = 0; k < 5; k++) sb.append(String.format("%.3f ", f(img, off + k * 4L)));
            sb.append("...");
            for (int k = 20; k < 22; k++) sb.append(String.format(" %.3f", f(img, off + k * 4L)));
            p.printf("  0x%x: [%s] refs=%d %s%n", off, sb.toString().trim(),
                    refsTo(toAddr(off)).size(), refsTo(toAddr(off)));
        }
        p.close();
    }

    // ==== D: 运行时数据区线索 ====
    private void d_dataSegScan() throws Exception {
        PrintWriter p = pw("33_dataseg.txt");
        p.println("=== D: 数据段 / 0x81000000 运行时区线索 ===");

        // D1. p7 里是否有指向 0x81000000 的指针（页表/栈/BSS）
        p.println("\n--- D1: 值 = 0x81000000 附近的标量 ---");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int n = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getLength() != 4) continue;
            Object v = d.getValue();
            if (!(v instanceof Number)) continue;
            long val = ((Number) v).longValue() & 0xFFFFFFFFL;
            if (val >= 0x80FFF000L && val <= 0x81010000L) {
                List<String> r = refsTo(d.getAddress());
                p.printf("  %s = 0x%08x refs=%d %s%n", d.getAddress(), val, r.size(), r);
                if (++n > 40) break;
            }
        }
        p.println("  found = " + n);

        // D2. 镜像的高熵区（可能是已初始化数据 vs 代码）
        p.println("\n--- D2: 每 256KB 的字符串密度（定位 rodata/data 边界）---");
        for (long off = 0; off < 0xc400000L; off += 0x40000L) {
            Address a = toAddr(off);
            if (a.getOffset() >= currentProgram.getMaxAddress().getOffset()) break;
            byte[] buf = new byte[0x40000];
            try { currentProgram.getMemory().getBytes(a, buf); } catch (Exception e) { continue; }
            int printable = 0, zeros = 0;
            for (byte b : buf) {
                if (b == 0) zeros++;
                else if (b >= 32 && b < 127) printable++;
            }
            p.printf("  0x%06x-0x%06x  可打印=%5.1f%%  零=%5.1f%%%n",
                    off, off + 0x40000, 100.0 * printable / buf.length, 100.0 * zeros / buf.length);
        }
        p.close();
    }

    // ---- float helpers (Ghidra Memory 没有 getFloat, 自己从 buffer 读) ----
    private byte[] _img;
    private byte[] readImage() {
        if (_img != null) return _img;
        long max = currentProgram.getMaxAddress().getOffset();
        _img = new byte[(int) (max + 1)];
        try { currentProgram.getMemory().getBytes(toAddr(0), _img); }
        catch (Exception e) { /* 超出部分保持 0 */ }
        return _img;
    }

    private float f(byte[] img, long off) {
        int i = (int) off;
        if (i < 0 || i + 4 > img.length) return Float.NaN;
        return Float.intBitsToFloat(
            (img[i] & 0xff) | ((img[i+1] & 0xff) << 8) | ((img[i+2] & 0xff) << 16) | ((img[i+3] & 0xff) << 24));
    }

    private String floats(byte[] img, long off, int n, String fmt) {
        StringBuilder sb = new StringBuilder();
        for (int k = 0; k < n; k++) sb.append(String.format(fmt + " ", f(img, off + k * 4L)));
        return sb.toString().trim();
    }

    private List<long[]> findFloatRuns(byte[] img, int n, double maxAbs) {
        List<long[]> out = new ArrayList<>();
        int i = 0;
        while (i + n * 4 <= img.length) {
            boolean ok = true;
            for (int k = 0; k < n; k++) {
                float v = f(img, i + k * 4L);
                if (Float.isNaN(v) || Float.isInfinite(v) || Math.abs(v) > maxAbs) { ok = false; break; }
            }
            if (ok) { out.add(new long[]{i}); i += n * 4; } else i += 4;
        }
        return out;
    }

    private List<Long> findUnitRuns(byte[] img, int n) {
        List<Long> out = new ArrayList<>();
        int i = 0;
        while (i + n * 4 <= img.length) {
            boolean ok = true;
            for (int k = 0; k < n; k++) {
                float v = f(img, i + k * 4L);
                if (Float.isNaN(v) || Float.isInfinite(v) || v < -0.001f || v > 1.001f) { ok = false; break; }
            }
            if (ok) { out.add((long) i); i += n * 4; } else i += 4;
        }
        return out;
    }

    // ---- utils ----
    private Iterable<Reference> allRefs() {
        List<Reference> all = new ArrayList<>();
        ReferenceIterator rit = currentProgram.getReferenceManager().getReferenceIterator(toAddr(0));
        while (rit.hasNext()) all.add(rit.next());
        return all;
    }

    private String scalarStr(long a) {
        try {
            return "0x" + Long.toHexString(currentProgram.getMemory().getInt(toAddr(a)) & 0xFFFFFFFFL);
        } catch (Exception e) { return "(undef)"; }
    }

    private String decomp(Function f) {
        String key = f.getEntryPoint().toString();
        if (cache.containsKey(key)) return cache.get(key);
        String r = null;
        try {
            DecompileResults res = di.decompileFunction(f, 30, monitor);
            if (res != null && res.decompileCompleted()) r = res.getDecompiledFunction().getC();
        } catch (Exception e) { r = null; }
        cache.put(key, r);
        return r;
    }

    private PrintWriter pw(String n) throws Exception {
        return new PrintWriter(new FileWriter(new File(dir, n), false));
    }

    private List<String> refsTo(Address a) {
        List<String> out = new ArrayList<>();
        ReferenceIterator rit = currentProgram.getReferenceManager().getReferencesTo(a);
        while (rit.hasNext()) {
            Reference r = rit.next();
            Function f = getFunctionContaining(r.getFromAddress());
            out.add(f == null ? r.getFromAddress().toString() : f.getName());
            if (out.size() >= 6) break;
        }
        return out;
    }
}
