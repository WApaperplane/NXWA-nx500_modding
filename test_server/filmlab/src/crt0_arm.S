/* crt0_arm.S —— 给「相机 ABI」用的最小 crt 启动代码（替代 gcc 自带的 Scrt1.o）
 *
 * ★ 为什么必须自备（2026-10-11 实测）：
 *   宿主 gcc-13 的 crt1.o 里 `_start` 引用的是 `__libc_start_main@GLIBC_2.34`
 *   （glibc 2.34 改了 argc/argv 传递方式并升了版本号），而相机是 glibc 2.13，
 *   于是 chroot 里直接报：
 *       /lib/libc.so.6: version `GLIBC_2.34' not found
 *   而相机自己的程序（如 /usr/bin/st）用的是 `__libc_start_main@GLIBC_2.4`
 *   —— 与相机 libc 完全匹配。⇒ 只要**不用宿主的 crt1.o**、并**直接链相机的 libc**，
 *   版本需求就整体落到 GLIBC_2.4/2.13，问题消失。
 *
 * 调用约定：__libc_start_main(main, argc, argv, init, fini, rtld_fini, stack_end)
 *   r0..r3 = main, argc, argv, init ；其后 3 个参数走栈（低地址在前）。
 *   推 4 个字（保留 8 字节栈对齐）⇒ 第 8 个字是填充位，被忽略。
 */
	.syntax unified
	.arm
	.text
	.globl _start
	.type  _start, %function
_start:
	mov	fp, #0			/* 断链回溯终止 */
	mov	lr, #0
	ldr	r1, [sp]		/* argc */
	add	r2, sp, #4		/* argv */
	ldr	r0, =main		/* main */
	mov	r3, #0			/* init     = NULL（本程序无 .init_array 需求） */
	mov	r4, #0			/* fini     = NULL */
	mov	r5, #0			/* rtld_fini= NULL（由 ld.so 自行处理） */
	mov	r6, sp			/* stack_end= 入口 sp */
	push	{r4, r5, r6, r7}	/* 第 5/6/7 个参数 + 1 个对齐填充 */
	bl	__libc_start_main
	bl	abort			/* __libc_start_main 正常不返回 */
	.size _start, .-_start

	/* 供 glibc 启动代码引用的边界符号（最小集） */
	.globl __data_start
__data_start:
	.globl data_start
data_start:
	.globl __bss_start__
__bss_start__:
	.globl __bss_end__
__bss_end__:
	.globl __end__
__end__:
	.weak __gmon_start__

/* 声明"不需要可执行栈"，否则内核会打印
   `process '...' started with executable stack`（无害但会污染证据日志） */
	.section .note.GNU-stack,"",%progbits
