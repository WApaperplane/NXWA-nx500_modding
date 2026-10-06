// P7 固件逆向导出脚本 (Ghidra headless)
// 目的: 解决"哪里是代码"的问题 —— 输出段布局 / 函数清单 / 字符串交叉引用
// 用法: -postScript DumpP7.java <输出目录>
//@category NX-KS2
//@author NX-KS2

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.data.*;
import java.io.*;
import java.util.*;

public class DumpP7 extends GhidraScript {

    private PrintWriter out;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = args.length > 0 ? args[0] : ".";
        File od = new File(outDir);
        od.mkdirs();
        println("DumpP7 -> " + od.getAbsolutePath());

        dumpHeader(od);
        dumpMemoryBlocks(od);
        dumpFunctions(od);
        dumpCrossRefs(od);
        dumpStrings(od);
        dumpScalarRefs(od);

        println("DumpP7 done.");
    }

    private PrintWriter w(String name) throws Exception {
        return new PrintWriter(new FileWriter(new File(lastDir(), name), false));
    }

    private File _dir;
    private File lastDir() { return _dir; }

    private void dumpHeader(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("00_header.txt");
        p.println("=== p7 固件基本信息 ===");
        p.println("language   : " + currentProgram.getLanguageID());
        p.println("compiler   : " + currentProgram.getCompilerSpec().getCompilerSpecID());
        p.println("imageBase  : " + currentProgram.getImageBase());
        p.println("minAddr    : " + currentProgram.getMinAddress());
        p.println("maxAddr    : " + currentProgram.getMaxAddress());
        p.println("execPath   : " + currentProgram.getExecutablePath());
        p.println("md5        : " + currentProgram.getExecutableMD5());
        p.println("memoryBlks : " + currentProgram.getMemory().getBlocks().length);
        // TMode 说明: A32 vs Thumb 由 language 决定
        p.close();
    }

    private void dumpMemoryBlocks(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("01_memory_blocks.txt");
        p.println("=== 段布局 (解决\"哪里是代码\") ===");
        p.printf("%-12s %-12s %-12s %-10s %-8s %s%n",
                "start", "end", "size", "perm", "type", "initialized");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            long size = b.getSize();
            String perm = (b.isRead() ? "r" : "-") + (b.isWrite() ? "w" : "-") + (b.isExecute() ? "x" : "-");
            p.printf("%-12s %-12s %-12d %-10s %-8s %s%n",
                    b.getStart(), b.getEnd(), size, perm,
                    b.getType(), b.isInitialized() ? "yes" : "NO");
        }
        p.close();
    }

    private void dumpFunctions(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("02_functions.txt");
        FunctionManager fm = currentProgram.getFunctionManager();
        List<Function> fs = new ArrayList<>();
        for (Function f : fm.getFunctions(true)) fs.add(f);
        p.println("=== 函数清单 ===");
        p.println("total functions = " + fs.size());
        p.println("addr\tsize\tname\tthunk?\texternal?");
        for (Function f : fs) {
            p.printf("%s\t%d\t%s\t%s\t%s%n",
                    f.getEntryPoint(), f.getBody().getNumAddresses(),
                    f.getName(), f.isThunk(), f.isExternal());
        }
        p.close();
    }

    // 关键: 找出"被字符串引用到的函数" —— 这是绕开符号名反查的关键
    private void dumpCrossRefs(PrintWriter p, Address addr, String label) {
        ReferenceManager rm = currentProgram.getReferenceManager();
        // Ghidra 12 的 getReferencesTo 返回 Iterator（不是数组）
        ReferenceIterator rit = rm.getReferencesTo(addr);
        int n = 0;
        List<String> lines = new ArrayList<>();
        while (rit.hasNext()) {
            Reference r = rit.next();
            Address from = r.getFromAddress();
            Function f = getFunctionContaining(from);
            lines.add(String.format("  %s  %s   %s", from,
                    f == null ? "(no func)" : f.getName(),
                    r.getReferenceType()));
            n++;
        }
        if (n == 0) return;
        p.println("--- refs to " + label + " @ " + addr + " (" + n + ") ---");
        for (String s : lines) p.println(s);
    }

    private void dumpCrossRefs(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("03_string_xrefs.txt");
        p.println("=== 关键字符串的交叉引用（验证\"死数据\"假设）===");

        String[] keys = {
            "SetLiveviewParam2Monitor", "StartLiveviewParameterMonitor",
            "CBackend_Ipc_Parameter", "CBackend_Ipc_Factory_NX1",
            "CBackendParameterMonitor", "IpcDebugProcess", "setIPC_UD_Material",
            "CIpcGamma", "CIpcWB", "CIpcColor",
            "CMaterial_NX1_Still_IPC_Main", "CMaterial_IPC_LiveviewMtoM",
            "iGamma2", "m_YGammaOut_Diff", "m_RGBGammaX_EVC",
            "TC_LOW_ANCHOR_X00", "CC_RGBL_MAT_00", "WB_GAIN2_RR",
            "GAMMA_INDEX", "MOVIE_GAMMA_CONTROL",
            "LUT_Load", "LUT_ChangeAddress", "YCC_SET"
        };

        // 建立 地址->字符串 索引
        Address found_any = null;
        for (String k : keys) {
            Address a = findString(k);
            if (a == null) { p.println("MISSING: " + k); continue; }
            if (found_any == null) found_any = a;
            p.printf("FOUND %-34s @ %s  %n", k, a);
            dumpCrossRefs(p, a, k);
        }
        p.close();
    }

    private Address findString(String s) {
        // 精确匹配 NUL 结尾
        byte[] target;
        try { target = s.getBytes("ASCII"); } catch (Exception e) { return null; }
        byte[] withNul = Arrays.copyOf(target, target.length + 1);
        Memory mem = currentProgram.getMemory();
        Address found = null;
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized()) continue;
            try {
                Address addr = b.getStart();
                long n = b.getSize();
                byte[] buf = new byte[(int) Math.min(n, 0x1000000)];
                mem.getBytes(addr, buf);
                for (int i = 0; i + withNul.length <= buf.length; i++) {
                    boolean ok = true;
                    for (int j = 0; j < withNul.length; j++) {
                        if (buf[i + j] != withNul[j]) { ok = false; break; }
                    }
                    if (ok) { found = addr.add(i); break; }
                }
            } catch (Exception e) { /* block 读取失败则跳过 */ }
            if (found != null) return found;
        }
        return found;
    }

    private void dumpStrings(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("04_strings.txt");
        p.println("=== 已定义字符串 (Data/String) ===");
        p.println("addr\tlen\tvalue");
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        int n = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getDataType().getName().toLowerCase().contains("string")
                || d.getDataType().getName().toLowerCase().contains("unicode")) {
                Object v = d.getValue();
                String s = v == null ? "" : v.toString();
                p.printf("%s\t%d\t%s%n", d.getAddress(), d.getLength(),
                        s.replace("\n", "\\n"));
                n++;
            }
        }
        p.println("total defined strings = " + n);
        p.close();
    }

    // 扫 LDR-literal 引用 —— 这次有段边界做前提, 结果可信
    private void dumpScalarRefs(File od) throws Exception {
        _dir = od;
        PrintWriter p = w("05_scalar_refs.txt");
        p.println("=== 标量常量引用 (有段边界前提, 替代裸镜像位掩码扫描) ===");
        p.println("addr\trefCount\trefs");
        ReferenceManager rm = currentProgram.getReferenceManager();
        //遍历所有被引用 >=1 次的标量数据
        DataIterator it = currentProgram.getListing().getDefinedData(true);
        Map<String, List<String>> m = new TreeMap<>();
        int n = 0;
        while (it.hasNext()) {
            Data d = it.next();
            if (d.getLength() != 4) continue;
            ReferenceIterator rit = rm.getReferencesTo(d.getAddress());
            if (!rit.hasNext()) continue;
            List<String> fs = new ArrayList<>();
            while (rit.hasNext()) {
                Reference r = rit.next();
                Function f = getFunctionContaining(r.getFromAddress());
                fs.add(f == null ? r.getFromAddress().toString() : f.getName());
            }
            Object v = d.getValue();
            m.put(d.getAddress() + " = " + v, fs);
            n++;
        }
        for (Map.Entry<String, List<String>> e : m.entrySet()) {
            p.printf("%s\t%d\t%s%n", e.getKey(), e.getValue().size(), e.getValue());
        }
        p.println("total referenced scalars = " + n);
        p.close();
    }
}
