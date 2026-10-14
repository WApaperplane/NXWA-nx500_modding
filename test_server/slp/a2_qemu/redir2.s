@ redir2.s —— 0x4cd30 的改道指令：bl 0x80011530（替代原 bl 0xd6b20）
	.arch armv7-a
	.arm
	.text
	.global _start
_start:
	bl	0x80011530
