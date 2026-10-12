@ =====================================================================
@ C-2 桩 v2 —— di-camera-app handler 移植桩（拼接版）
@
@ 语义：handler(argc=r0, argv=r1)  ⇒  system("sh /opt/usr/nx-ks/f.sh " + argv[1..argc-1])
@   v1 的缺口：只执行 system(argv[1])，需短路径/符号链接，且单参数 ≤19 字符。
@   v2 用 FUN_000ca3a8 遗体（656B 可用：0xca3a8..0xca638）原地展开前缀拼接，
@   零 PATH 依赖 ⇒ `st app film apply 23` 自然可用。
@
@ 落点：vaddr 0xca3a8（= file 0xc23a8）
@ 汇编/链接（WSL NXKS2，见 test_server/dicam/build_stub_v2.sh）:
@   arm-linux-gnueabi-as -o stub_v2.o stub_v2.s
@   arm-linux-gnueabi-ld -Ttext=0xca3a8 -o stub_v2.elf stub_v2.o
@   arm-linux-gnueabi-objcopy -O binary -j .text stub_v2.elf stub_v2.bin
@ =====================================================================

    .syntax unified
    .arch armv7-a
    .arm
    .text

    .set    SYS_PLT, 0x000add08     @ system@plt（App 自带，已是 PLT 条目）
    .set    MOD_SH,  0x000f6d6f      @ 占位（未用）

    .global c2_stub_v2
c2_stub_v2:
    cmp     r0, #2                  @ argc >= 2 ?
    bxcc    lr                      @ 否则直接返回 r0（与原桩一致，无参数不动）
    push    {r4-r8, lr}
    sub     sp, sp, #256            @ 静态缓冲 buf[256]（8B 对齐）
    mov     r4, r1                  @ r4 = argv
    mov     r5, r0                  @ r5 = argc
    mov     r7, sp                  @ r7 = 写游标

    ldr     r8, =prefix             @ 拷贝固定前缀
.Lpfx:
    ldrb    r0, [r8], #1
    cmp     r0, #0
    beq     .Largs
    strb    r0, [r7], #1
    b       .Lpfx

.Largs:
    mov     r6, #1                  @ i = 1
.Lloop:
    cmp     r6, r5
    bge     .Ldone
    ldr     r0, [r4, r6, lsl #2]    @ r0 = argv[i]
.Lcopy:
    ldrb    r1, [r0], #1
    cmp     r1, #0
    beq     .Lsep
@ ---- ★ 参数净化（白名单：a-z A-Z 0-9 . _ + - /），其余一律替换为 '_' ----
@   为什么必须做：本桩把参数【拼进命令行】交给 system()（= /bin/sh -c），
@   若原样透传，则 "x; rm -rf /" 这类入参会取得 shell 解释权（实测已复现）。
@   净化后 shell 元字符（; | & $ ` ( ) < > " ' * ? 换行 空格…）全部失效。
@   注：空格不在白名单 ⇒ 多参数靠 .Lsep 自行插入的分隔空格，天然安全。
    cmp     r1, #0x30               @ '0'
    blt     .LchkA
    cmp     r1, #0x39               @ '9'
    ble     .Lkeep
.LchkA:
    cmp     r1, #0x41               @ 'A'
    blt     .Lchka
    cmp     r1, #0x5a               @ 'Z'
    ble     .Lkeep
.Lchka:
    cmp     r1, #0x61               @ 'a'
    blt     .Lchksym
    cmp     r1, #0x7a               @ 'z'
    ble     .Lkeep
.Lchksym:
    cmp     r1, #0x2e               @ '.'
    beq     .Lkeep
    cmp     r1, #0x5f               @ '_'
    beq     .Lkeep
    cmp     r1, #0x2b               @ '+'
    beq     .Lkeep
    cmp     r1, #0x2d               @ '-'
    beq     .Lkeep
    cmp     r1, #0x2f               @ '/'
    beq     .Lkeep
    mov     r1, #0x5f               @ 非法 → '_'
.Lkeep:
    strb    r1, [r7], #1
    b       .Lcopy
.Lsep:
    mov     r1, #0x20               @ ' '
    strb    r1, [r7], #1
    add     r6, r6, #1
    b       .Lloop

.Ldone:
    mov     r0, #0
    strb    r0, [r7]                @ NUL 收尾
    mov     r0, sp
    bl      SYS_PLT                 @ system(buf)
    add     sp, sp, #256
    pop     {r4-r8, pc}

    .ltorg                          @ 字面量池（=prefix 的地址在此）
prefix:
    .asciz  "sh /opt/usr/nx-ks/f.sh "
    .align  2
