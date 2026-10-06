//FindCapdtm.java —— 在 p7 里定位 capdtm 服务端：变量名表 + setvar/getvar 的 id 分派
//用法: -postScript FindCapdtm.java <outDir>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.data.*;
import ghidra.program.model.mem.*;
import ghidra.util.task.TaskMonitor;
import java.io.*;
import java.util.*;

public class FindCapdtm extends GhidraScript {
    private String outDir;

    @Override
    protected void run() throws Exception {
        String[] a = getScriptArgs();
        outDir = (a.length > 0) ? a[0] : "E:/ghidra_out";
        new File(outDir).mkdirs();
        PrintWriter p = w("50_capdtm.txt");

        // ── 1. 锚点串地址（实测）──
        long[] ANCH = {
            0x6f3710,   // "capdtm"
            0x6f3791,   // "setusr"
            0x6f37a1,   // "setvar"
            0x6f8440,   // "VARIABLE_WBCOLORTEMP"
            0x6f8458,   // "VARIABLE_WBADJUST"
            0x6f8514,   // "VARIABLE_PWCOLOR"
            0x6f3f5c,   // "USERDATA_"
            0x6f5870,   // "PW_STANDARD"
            0x6f5354,   // "WB_MANUAL"
            0x57262f,   // "DataManagement"
        };
        p.println("=== 1. anchor string xrefs ===");
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (long a2 : ANCH) {
            Address ad = toAddr(a2);
            ReferenceIterator it = rm.getReferencesTo(ad);
            List<String> fs = new ArrayList<>();
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                fs.add((f == null ? "(nofunc)" : f.getName()) + "@" + r.getFromAddress());
            }
            p.printf("  0x%08x %-24s refs=%d %s%n", a2, strAt(ad, 24), fs.size(), fs);
        }

        // ── 2. 变量名表完整枚举（VARIABLE_* / USERDATA_* / WB_ / PW_）──
        p.println("\n=== 2. VARIABLE_/USERDATA_ name table ===");
        Address lo = toAddr(0x6f3e00), hi = toAddr(0x6f8800);
        int nv = 0, nu = 0;
        for (Address a2 = lo; a2.compareTo(hi) < 0; a2 = a2.add(1)) {
            Data d = getDataAt(a2);
            if (d == null || d.getLength() < 4) continue;
            String s = strAt(a2, 28);
            if (s.startsWith("VARIABLE_")) { p.printf("  VAR0x%x %s%n", a2.getOffset(), s); nv++; }
            else if (s.startsWith("USERDATA_")) { p.printf("  USR0x%x %s%n", a2.getOffset(), s); nu++; }
        }
        p.printf("  --- VARIABLE_=%d  USERDATA_=%d%n", nv, nu);

        // ── 3. 找 varlist/setvar 的实现函数（含这些串的函数）──
        p.println("\n=== 3. functions containing capdtm strings (decompiled) ===");
        Set<Function> targets = new LinkedHashSet<>();
        String[] keys = {"capdtm", "setusr", "setvar", "VARIABLE_WBCOLORTEMP",
                         "varlist", "usrlist", "getvar", "getusr"};
        for (String k : keys) {
            Address ad = findBytes(k);
            if (ad == null) { p.println("  key not found: " + k); continue; }
            ReferenceIterator it = rm.getReferencesTo(ad);
            while (it.hasNext()) {
                Function f = getFunctionContaining(it.next().getFromAddress());
                if (f != null) targets.add(f);
            }
        }
        p.println("  target functions: " + targets.size());
        int fi = 0;
        for (Function f : targets) {
            p.printf("%n--- [%d] %s @ %s size=%d ---%n", fi++, f.getName(),
                     f.getEntryPoint(), f.getBody().getNumAddresses());
            try {
                String code = new DecompInterface().decompileFunction(f, 30, monitor).getDecompiledFunction().getC();
                p.println(code.length() > 9000 ? code.substring(0, 9000) + "\n...[truncated]" : code);
            } catch (Exception e) {
                p.println("  decompile failed: " + e);
            }
        }

        // ── 4. WBCOLORTEMP 名串的引用者里，谁在做 switch(id) ──
        p.println("\n=== 4. switch(id) candidates: funcs with many small compares ===");
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int scanned = 0;
        while (fit.hasNext() && scanned < 60000) {
            Function f = fit.next();
            scanned++;
            if (f.getBody().getNumAddresses() > 20000) continue;
            // 找 "VARIABLE_WBCOLORTEMP" 引用者里最可能做分派的
            Address ad = toAddr(0x6f8440);
            ReferenceIterator it = rm.getReferencesTo(ad);
            while (it.hasNext()) {
                Address from = it.next().getFromAddress();
                Function g = getFunctionContaining(from);
                if (g == null) continue;
                p.printf("  WBCOLORTEMP ref from %s in %s @ %s size=%d%n",
                         from, g.getName(), g.getEntryPoint(), g.getBody().getNumAddresses());
                try {
                    String code = new DecompInterface().decompileFunction(g, 30, monitor).getDecompiledFunction().getC();
                    p.println(code.length() > 6000 ? code.substring(0, 6000) : code);
                } catch (Exception e) { p.println("  decompile failed"); }
            }
        }
        p.printf("%nscanned %d functions%n", scanned);

        p.close();
        println("FindCapdtm -> " + outDir + "/50_capdtm.txt");
    }

    /** 逐地址扫描找串（p7 裸镜像上可靠；memory.findBytes 在此环境不可用） */
    private Address findBytes(String s) {
        byte[] pat = s.getBytes();
        Memory mem = currentProgram.getMemory();
        Address cur = toAddr(0x6f0000);
        Address end = toAddr(0x760000);
        byte[] buf = new byte[pat.length];
        while (cur != null && cur.compareTo(end) < 0) {
            try {
                mem.getBytes(cur, buf);
                boolean hit = true;
                for (int i = 0; i < pat.length; i++) {
                    if (buf[i] != pat[i]) { hit = false; break; }
                }
                if (hit) return cur;
            } catch (Exception e) { /* 越界 */ }
            cur = cur.add(1);
        }
        return null;
    }

    private String strAt(Address a, int max) {
        try {
            byte[] b = new byte[max];
            currentProgram.getMemory().getBytes(a, b);
            int n = 0; while (n < max && b[n] != 0) n++;
            return new String(b, 0, n);
        } catch (Exception e) { return "?"; }
    }

    private PrintWriter w(String name) throws Exception {
        return new PrintWriter(new FileWriter(new File(outDir, name), false));
    }
}
