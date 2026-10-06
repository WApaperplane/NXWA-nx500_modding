/* ===== _udd_ep_mc_rpath4_ctrl @ 0x0000dd38  size=628  ARM ===== */
  0000dd38:  push       {r4, fp, lr}
  0000dd3c:  add        fp, sp, #8
  0000dd40:  sub        sp, sp, #0xcc
  0000dd44:  str        r0, [fp, #-0xd0]
  0000dd48:  str        r1, [fp, #-0xd4]
  0000dd4c:  ldr        r4, [pc, #0x24c]
  0000dd50:  add        r4, pc, r4
  0000dd54:  sub        r2, fp, #0xcc
  0000dd58:  mov        r3, #0xb8
  0000dd5c:  mov        r0, r2
  0000dd60:  mov        r1, #0
  0000dd64:  mov        r2, r3
  0000dd68:  bl         #0x8984   // ->@plt memset
  0000dd6c:  mov        r3, #0x17
  0000dd70:  str        r3, [fp, #-0x10]
  0000dd74:  ldr        r3, [fp, #-0xd0]
  0000dd78:  ldr        r3, [r3, #0x24]
  0000dd7c:  uxtb       r3, r3
  0000dd80:  cmp        r3, #0
  0000dd84:  beq        #0xdda0
  0000dd88:  ldr        r3, [fp, #-0xd0]
  0000dd8c:  ldr        r3, [r3, #0x24]
  0000dd90:  uxtb       r2, r3
  0000dd94:  ldr        r3, [fp, #-0x10]
  0000dd98:  cmp        r2, r3
  0000dd9c:  blt        #0xddac
  0000dda0:  movw       r3, #0xfe08
  0000dda4:  movt       r3, #0xffff
  0000dda8:  b          #0xdf94
  0000ddac:  sub        r3, fp, #0xcc
  0000ddb0:  ldr        r0, [fp, #-0xd0]
  0000ddb4:  mov        r1, r3
  0000ddb8:  ldr        r2, [fp, #-0xd4]
  0000ddbc:  bl         #0x8ac8   // ->@plt _udd_ep_mc_ring_size_set
  0000ddc0:  ldrb       r3, [fp, #-0xb5]
  0000ddc4:  orr        r3, r3, #0x10
  0000ddc8:  strb       r3, [fp, #-0xb5]
  0000ddcc:  ldrb       r3, [fp, #-0xb5]
  0000ddd0:  orr        r3, r3, #0x20
  0000ddd4:  strb       r3, [fp, #-0xb5]
  0000ddd8:  ldr        r3, [fp, #-0xd0]
  0000dddc:  ldr        r2, [r3, #0x24]
  0000dde0:  movw       r3, #0x4004
  0000dde4:  cmp        r2, r3
  0000dde8:  ble        #0xdeb8
  0000ddec:  ldr        r3, [fp, #-0xd0]
  0000ddf0:  ldr        r3, [r3, #0x18]
  0000ddf4:  cmp        r3, #8
  0000ddf8:  bls        #0xdeb8
  0000ddfc:  ldrb       r3, [fp, #-0x5c]
  0000de00:  orr        r3, r3, #1
  0000de04:  strb       r3, [fp, #-0x5c]
  0000de08:  ldr        r3, [fp, #-0xd0]
  0000de0c:  ldr        r3, [r3, #0x18]
  0000de10:  uxtb       r3, r3
  0000de14:  and        r3, r3, #0xf
  0000de18:  uxtb       r2, r3
  0000de1c:  ldrb       r3, [fp, #-0x54]
  0000de20:  bfi        r3, r2, #4, #4
  0000de24:  strb       r3, [fp, #-0x54]
  0000de28:  ldr        r3, [fp, #-0xd0]
  0000de2c:  ldr        r3, [r3, #0x18]
  0000de30:  uxtb       r3, r3
  0000de34:  and        r3, r3, #0xf
  0000de38:  uxtb       r2, r3
  0000de3c:  ldrb       r3, [fp, #-0x53]
  0000de40:  bfi        r3, r2, #0, #4
  0000de44:  strb       r3, [fp, #-0x53]
  0000de48:  ldr        r3, [fp, #-0xd0]
  0000de4c:  ldr        r3, [r3, #0x18]
  0000de50:  uxtb       r3, r3
  0000de54:  and        r3, r3, #0xf
  0000de58:  uxtb       r2, r3
  0000de5c:  ldrb       r3, [fp, #-0x53]
  0000de60:  bfi        r3, r2, #4, #4
  0000de64:  strb       r3, [fp, #-0x53]
  0000de68:  ldr        r3, [fp, #-0xd4]
  0000de6c:  ldr        r3, [r3]
  0000de70:  ldr        r2, [fp, #-0xd0]
  0000de74:  ldr        r2, [r2, #0x18]
  0000de78:  mov        r1, #1
  0000de7c:  lsl        r2, r1, r2
  0000de80:  uxth       r2, r2
  0000de84:  sub        r2, r2, #1
  0000de88:  uxth       r2, r2
  0000de8c:  strh       r2, [r3, #0xe]
  0000de90:  ldr        r3, [fp, #-0xd4]
  0000de94:  ldr        r3, [r3, #4]
  0000de98:  ldr        r2, [fp, #-0xd0]
  0000de9c:  ldr        r2, [r2, #0x18]
  0000dea0:  mov        r1, #1
  0000dea4:  lsl        r2, r1, r2
  0000dea8:  uxth       r2, r2
  0000deac:  sub        r2, r2, #1
  0000deb0:  uxth       r2, r2
  0000deb4:  strh       r2, [r3, #0xa]
  0000deb8:  ldr        r3, [fp, #-0xd0]
  0000debc:  ldr        r2, [r3, #0x24]
  0000dec0:  movw       r3, #0x4109
  0000dec4:  cmp        r2, r3
  0000dec8:  bne        #0xdf10
  0000decc:  ldr        r3, [pc, #0xd0]
  0000ded0:  ldr        r3, [r4, r3]
  0000ded4:  ldr        r3, [r3]
  0000ded8:  add        r3, r3, #0x730
  0000dedc:  add        r3, r3, #4
  0000dee0:  ldr        r3, [r3]
  0000dee4:  uxtb       r3, r3
  0000dee8:  str        r3, [fp, #-0x14]
  0000deec:  ldr        r3, [fp, #-0xd4]
  0000def0:  ldr        r2, [r3]
  0000def4:  ldr        r3, [fp, #-0x14]
  0000def8:  uxtb       r3, r3
  0000defc:  sub        r3, r3, #1
  0000df00:  uxtb       r1, r3
  0000df04:  ldrb       r3, [r2, #4]
  0000df08:  bfi        r3, r1, #0, #8
  0000df0c:  strb       r3, [r2, #4]
  0000df10:  ldr        r3, [fp, #-0xd0]
  0000df14:  ldr        r3, [r3, #0x24]
  0000df18:  uxtb       r2, r3
  0000df1c:  ldr        r3, [pc, #0x84]
  0000df20:  add        r3, pc, r3
  0000df24:  ldr        r3, [r3, r2, lsl #2]
  0000df28:  sub        r2, fp, #0xcc
  0000df2c:  mov        r0, r2
  0000df30:  ldr        r1, [fp, #-0xd4]
  0000df34:  blx        r3
  0000df38:  ldr        r3, [fp, #-0xd0]
  0000df3c:  ldr        r2, [r3, #0x24]
  0000df40:  movw       r3, #0x4115
  0000df44:  cmp        r2, r3
  0000df48:  bne        #0xdf5c
  0000df4c:  ldrb       r3, [fp, #-0x53]
  0000df50:  mov        r2, #0xb
  0000df54:  bfi        r3, r2, #4, #4
  0000df58:  strb       r3, [fp, #-0x53]
  0000df5c:  ldr        r3, [fp, #-0xd0]
  0000df60:  ldr        r2, [r3, #0x24]
  0000df64:  movw       r3, #0x4215
  0000df68:  cmp        r2, r3
  0000df6c:  bne        #0xdf80
  0000df70:  ldrb       r3, [fp, #-0x53]
  0000df74:  mov        r2, #0xb
  0000df78:  bfi        r3, r2, #0, #4
  0000df7c:  strb       r3, [fp, #-0x53]
  0000df80:  sub        r3, fp, #0xcc
  0000df84:  ldr        r0, [fp, #-0xd0]
  0000df88:  mov        r1, r3
  0000df8c:  bl         #0x8e70   // ->@plt _udd_ep_mc_common_reg_set
  0000df90:  mov        r3, r0
  0000df94:  mov        r0, r3
  0000df98:  sub        sp, fp, #8
  0000df9c:  pop        {r4, fp, pc}
  0000dfa0:  andeq      ip, r3, r8, ror #10
  0000dfa4:  andeq      r0, r0, r0, ror #10
  0000dfa8:  andeq      ip, r3, r4, ror #19

/* ===== _udd_ep_mc_get_default_param2 @ 0x00011ec8  size=72  ARM ===== */
  00011ec8:  push       {fp, lr}
  00011ecc:  add        fp, sp, #4
  00011ed0:  sub        sp, sp, #8
  00011ed4:  str        r0, [fp, #-8]
  00011ed8:  str        r1, [fp, #-0xc]
  00011edc:  ldr        r3, [fp, #-8]
  00011ee0:  uxtb       r2, r3
  00011ee4:  ldr        r3, [pc, #0x20]
  00011ee8:  add        r3, pc, r3
  00011eec:  ldr        r3, [r3, r2, lsl #2]
  00011ef0:  ldr        r0, [fp, #-8]
  00011ef4:  ldr        r1, [fp, #-0xc]
  00011ef8:  blx        r3
  00011efc:  mov        r3, #0
  00011f00:  mov        r0, r3
  00011f04:  sub        sp, fp, #4
  00011f08:  pop        {fp, pc}
  00011f0c:  andeq      sb, r3, r4, asr #2

/* ===== _udd_ep_mc_rpath1_ctrl @ 0x00021008  size=248  ARM ===== */
  00021008:  push       {r4, fp, lr}
  0002100c:  add        fp, sp, #8
  00021010:  sub        sp, sp, #0xcc
  00021014:  str        r0, [fp, #-0xd0]
  00021018:  str        r1, [fp, #-0xd4]
  0002101c:  ldr        r4, [pc, #0xd0]
  00021020:  add        r4, pc, r4
  00021024:  sub        r2, fp, #0xc8
  00021028:  mov        r3, #0xb8
  0002102c:  mov        r0, r2
  00021030:  mov        r1, #0
  00021034:  mov        r2, r3
  00021038:  bl         #0x8984   // ->@plt memset
  0002103c:  mov        r3, #8
  00021040:  str        r3, [fp, #-0x10]
  00021044:  ldr        r3, [fp, #-0xd0]
  00021048:  ldr        r3, [r3, #0x24]
  0002104c:  uxtb       r2, r3
  00021050:  ldr        r3, [fp, #-0x10]
  00021054:  cmp        r2, r3
  00021058:  blt        #0x21068
  0002105c:  movw       r3, #0xfe08
  00021060:  movt       r3, #0xffff
  00021064:  b          #0x210e8
  00021068:  sub        r3, fp, #0xc8
  0002106c:  ldr        r0, [fp, #-0xd0]
  00021070:  mov        r1, r3
  00021074:  ldr        r2, [fp, #-0xd4]
  00021078:  bl         #0x8ac8   // ->@plt _udd_ep_mc_ring_size_set
  0002107c:  ldr        r3, [pc, #0x74]
  00021080:  ldr        r3, [r4, r3]
  00021084:  ldr        r3, [r3]
  00021088:  add        r3, r3, #0x7c
  0002108c:  mov        r2, #0
  00021090:  str        r2, [r3]
  00021094:  ldrb       r3, [fp, #-0xb1]
  00021098:  orr        r3, r3, #0x10
  0002109c:  strb       r3, [fp, #-0xb1]
  000210a0:  ldrb       r3, [fp, #-0xb1]
  000210a4:  orr        r3, r3, #0x20
  000210a8:  strb       r3, [fp, #-0xb1]
  000210ac:  ldr        r3, [fp, #-0xd0]
  000210b0:  ldr        r3, [r3, #0x24]
  000210b4:  uxtb       r2, r3
  000210b8:  ldr        r3, [pc, #0x3c]
  000210bc:  add        r3, pc, r3
  000210c0:  ldr        r3, [r3, r2, lsl #2]
  000210c4:  sub        r2, fp, #0xc8
  000210c8:  mov        r0, r2
  000210cc:  ldr        r1, [fp, #-0xd4]
  000210d0:  blx        r3
  000210d4:  sub        r3, fp, #0xc8
  000210d8:  ldr        r0, [fp, #-0xd0]
  000210dc:  mov        r1, r3
  000210e0:  bl         #0x8e70   // ->@plt _udd_ep_mc_common_reg_set
  000210e4:  mov        r3, r0
  000210e8:  mov        r0, r3
  000210ec:  sub        sp, fp, #8
  000210f0:  pop        {r4, fp, pc}
  000210f4:  muleq      r2, r8, r2
  000210f8:  andeq      r0, r0, r0, ror #10
  000210fc:  andeq      sl, r2, r4

/* ===== _udd_ep_mc_rpath3_ctrl @ 0x00022ed4  size=268  ARM ===== */
  00022ed4:  push       {r4, fp, lr}
  00022ed8:  add        fp, sp, #8
  00022edc:  sub        sp, sp, #0xcc
  00022ee0:  str        r0, [fp, #-0xd0]
  00022ee4:  str        r1, [fp, #-0xd4]
  00022ee8:  ldr        r4, [pc, #0xe4]
  00022eec:  add        r4, pc, r4
  00022ef0:  sub        r2, fp, #0xc8
  00022ef4:  mov        r3, #0xb8
  00022ef8:  mov        r0, r2
  00022efc:  mov        r1, #0
  00022f00:  mov        r2, r3
  00022f04:  bl         #0x8984   // ->@plt memset
  00022f08:  mov        r3, #6
  00022f0c:  str        r3, [fp, #-0x10]
  00022f10:  ldr        r3, [fp, #-0xd0]
  00022f14:  ldr        r3, [r3, #0x24]
  00022f18:  uxtb       r3, r3
  00022f1c:  cmp        r3, #0
  00022f20:  beq        #0x22f3c
  00022f24:  ldr        r3, [fp, #-0xd0]
  00022f28:  ldr        r3, [r3, #0x24]
  00022f2c:  uxtb       r2, r3
  00022f30:  ldr        r3, [fp, #-0x10]
  00022f34:  cmp        r2, r3
  00022f38:  blt        #0x22f48
  00022f3c:  movw       r3, #0xfe08
  00022f40:  movt       r3, #0xffff
  00022f44:  b          #0x22fc8
  00022f48:  sub        r3, fp, #0xc8
  00022f4c:  ldr        r0, [fp, #-0xd0]
  00022f50:  mov        r1, r3
  00022f54:  ldr        r2, [fp, #-0xd4]
  00022f58:  bl         #0x8ac8   // ->@plt _udd_ep_mc_ring_size_set
  00022f5c:  ldr        r3, [pc, #0x74]
  00022f60:  ldr        r3, [r4, r3]
  00022f64:  ldr        r3, [r3]
  00022f68:  add        r3, r3, #0x7c
  00022f6c:  mov        r2, #0
  00022f70:  str        r2, [r3]
  00022f74:  ldrb       r3, [fp, #-0xb1]
  00022f78:  orr        r3, r3, #0x10
  00022f7c:  strb       r3, [fp, #-0xb1]
  00022f80:  ldrb       r3, [fp, #-0xb1]
  00022f84:  orr        r3, r3, #0x20
  00022f88:  strb       r3, [fp, #-0xb1]
  00022f8c:  ldr        r3, [fp, #-0xd0]
  00022f90:  ldr        r3, [r3, #0x24]
  00022f94:  uxtb       r2, r3
  00022f98:  ldr        r3, [pc, #0x3c]
  00022f9c:  add        r3, pc, r3
  00022fa0:  ldr        r3, [r3, r2, lsl #2]
  00022fa4:  sub        r2, fp, #0xc8
  00022fa8:  mov        r0, r2
  00022fac:  ldr        r1, [fp, #-0xd4]
  00022fb0:  blx        r3
  00022fb4:  sub        r3, fp, #0xc8
  00022fb8:  ldr        r0, [fp, #-0xd0]
  00022fbc:  mov        r1, r3
  00022fc0:  bl         #0x8e70   // ->@plt _udd_ep_mc_common_reg_set
  00022fc4:  mov        r3, r0
  00022fc8:  mov        r0, r3
  00022fcc:  sub        sp, fp, #8
  00022fd0:  pop        {r4, fp, pc}
  00022fd4:  andeq      r7, r2, ip, asr #7
  00022fd8:  andeq      r0, r0, r0, ror #10
  00022fdc:  andeq      r8, r2, ip, asr #2

/* ===== _udd_ep_mc_get_default_param3 @ 0x0002d37c  size=72  ARM ===== */
  0002d37c:  push       {fp, lr}
  0002d380:  add        fp, sp, #4
  0002d384:  sub        sp, sp, #8
  0002d388:  str        r0, [fp, #-8]
  0002d38c:  str        r1, [fp, #-0xc]
  0002d390:  ldr        r3, [fp, #-8]
  0002d394:  uxtb       r2, r3
  0002d398:  ldr        r3, [pc, #0x20]
  0002d39c:  add        r3, pc, r3
  0002d3a0:  ldr        r3, [r3, r2, lsl #2]
  0002d3a4:  ldr        r0, [fp, #-8]
  0002d3a8:  ldr        r1, [fp, #-0xc]
  0002d3ac:  blx        r3
  0002d3b0:  mov        r3, #0
  0002d3b4:  mov        r0, r3
  0002d3b8:  sub        sp, fp, #4
  0002d3bc:  pop        {fp, pc}
  0002d3c0:  andeq      sp, r1, r4, lsl #29

/* ===== _udd_ep_mc_get_default_param1 @ 0x00033abc  size=72  ARM ===== */
  00033abc:  push       {fp, lr}
  00033ac0:  add        fp, sp, #4
  00033ac4:  sub        sp, sp, #8
  00033ac8:  str        r0, [fp, #-8]
  00033acc:  str        r1, [fp, #-0xc]
  00033ad0:  ldr        r3, [fp, #-8]
  00033ad4:  uxtb       r2, r3
  00033ad8:  ldr        r3, [pc, #0x20]
  00033adc:  add        r3, pc, r3
  00033ae0:  ldr        r3, [r3, r2, lsl #2]
  00033ae4:  ldr        r0, [fp, #-8]
  00033ae8:  ldr        r1, [fp, #-0xc]
  00033aec:  blx        r3
  00033af0:  mov        r3, #0
  00033af4:  mov        r0, r3
  00033af8:  sub        sp, fp, #4
  00033afc:  pop        {fp, pc}
  00033b00:  andeq      r7, r1, r4, asr #23

/* ===== _udd_ep_mc_ring_size_set @ 0x000344c8  size=316  ARM ===== */
  000344c8:  push       {fp, lr}
  000344cc:  add        fp, sp, #4
  000344d0:  sub        sp, sp, #0x28
  000344d4:  str        r0, [fp, #-0x20]
  000344d8:  str        r1, [fp, #-0x24]
  000344dc:  str        r2, [fp, #-0x28]
  000344e0:  ldr        r2, [fp, #-0x20]
  000344e4:  sub        r3, fp, #0xc
  000344e8:  ldm        r2, {r0, r1}
  000344ec:  stm        r3, {r0, r1}
  000344f0:  mov        r3, #0
  000344f4:  str        r3, [fp, #-0x14]
  000344f8:  mov        r3, #0
  000344fc:  str        r3, [fp, #-0x10]
  00034500:  mov        r3, #0
  00034504:  str        r3, [fp, #-0x1c]
  00034508:  mov        r3, #0
  0003450c:  str        r3, [fp, #-0x18]
  00034510:  ldr        r3, [fp, #-0x20]
  00034514:  ldr        r3, [r3, #0x24]
  00034518:  cmp        r3, #0x1000
  0003451c:  bne        #0x34550
  00034520:  ldr        r2, [fp, #-0xc]
  00034524:  ldr        r3, [fp, #-0x28]
  00034528:  ldr        r3, [r3]
  0003452c:  lsl        r3, r3, #1
  00034530:  rsb        r3, r3, r2
  00034534:  str        r3, [fp, #-0xc]
  00034538:  ldr        r2, [fp, #-8]
  0003453c:  ldr        r3, [fp, #-0x28]
  00034540:  ldr        r3, [r3, #4]
  00034544:  lsl        r3, r3, #1
  00034548:  rsb        r3, r3, r2
  0003454c:  str        r3, [fp, #-8]
  00034550:  ldr        r3, [fp, #-0x20]
  00034554:  ldr        r3, [r3, #0x28]
  00034558:  cmp        r3, #1
  0003455c:  beq        #0x34570
  00034560:  ldr        r3, [fp, #-0x20]
  00034564:  ldr        r3, [r3, #0x28]
  00034568:  cmp        r3, #2
  0003456c:  bne        #0x345a4
  00034570:  sub        r3, fp, #0xc
  00034574:  ldr        r0, [fp, #-0x20]
  00034578:  ldr        r1, [fp, #-0x24]
  0003457c:  mov        r2, r3
  00034580:  bl         #0x33fa0
  00034584:  ldr        r3, [fp, #-0x20]
  00034588:  ldr        r3, [r3, #0x10]
  0003458c:  lsl        r3, r3, #1
  00034590:  str        r3, [fp, #-0x14]
  00034594:  ldr        r3, [fp, #-0x20]
  00034598:  ldr        r3, [r3, #0x14]
  0003459c:  lsl        r3, r3, #1
  000345a0:  str        r3, [fp, #-0x10]
  000345a4:  ldr        r3, [fp, #-0x20]
  000345a8:  ldr        r3, [r3, #0x28]
  000345ac:  cmp        r3, #1
  000345b0:  beq        #0x345e8
  000345b4:  sub        r3, fp, #0xc
  000345b8:  ldr        r0, [fp, #-0x20]
  000345bc:  ldr        r1, [fp, #-0x24]
  000345c0:  mov        r2, r3
  000345c4:  bl         #0x3420c
  000345c8:  ldr        r3, [fp, #-0x20]
  000345cc:  ldr        r3, [r3, #0x10]
  000345d0:  lsl        r3, r3, #1
  000345d4:  str        r3, [fp, #-0x1c]
  000345d8:  ldr        r3, [fp, #-0x20]
  000345dc:  ldr        r3, [r3, #0x14]
  000345e0:  lsl        r3, r3, #1
  000345e4:  str        r3, [fp, #-0x18]
  000345e8:  sub        r2, fp, #0x14
  000345ec:  sub        r3, fp, #0x1c
  000345f0:  mov        r0, r2
  000345f4:  mov        r1, r3
  000345f8:  bl         #0x8cd8   // ->@plt d5_ep_mc_set_overlap_margin
  000345fc:  sub        sp, fp, #4
  00034600:  pop        {fp, pc}

/* ===== _udd_ep_mc_common_reg_set @ 0x0003485c  size=1896  ARM ===== */
  0003485c:  push       {r4, fp, lr}
  00034860:  add        fp, sp, #8
  00034864:  sub        sp, sp, #0x14
  00034868:  str        r0, [fp, #-0x18]
  0003486c:  str        r1, [fp, #-0x1c]
  00034870:  ldr        r4, [pc, #0x744]
  00034874:  add        r4, pc, r4
  00034878:  ldr        r3, [fp, #-0x1c]
  0003487c:  ldrb       r3, [r3, #0x14]
  00034880:  ubfx       r3, r3, #0, #6
  00034884:  uxtb       r3, r3
  00034888:  str        r3, [fp, #-0x14]
  0003488c:  ldr        r3, [fp, #-0x18]
  00034890:  ldr        r2, [r3, #0x24]
  00034894:  movw       r3, #0x5016
  00034898:  cmp        r2, r3
  0003489c:  beq        #0x34984
  000348a0:  ldr        r3, [fp, #-0x1c]
  000348a4:  mvn        r2, #0
  000348a8:  strb       r2, [r3, #0x90]
  000348ac:  ldr        r3, [fp, #-0x1c]
  000348b0:  mvn        r2, #0
  000348b4:  strb       r2, [r3, #0x99]
  000348b8:  ldr        r3, [fp, #-0x1c]
  000348bc:  mvn        r2, #0
  000348c0:  strb       r2, [r3, #0x91]
  000348c4:  ldr        r3, [fp, #-0x1c]
  000348c8:  mvn        r2, #0
  000348cc:  strb       r2, [r3, #0x9a]
  000348d0:  ldr        r3, [fp, #-0x1c]
  000348d4:  mvn        r2, #0
  000348d8:  strb       r2, [r3, #0x92]
  000348dc:  ldr        r3, [fp, #-0x1c]
  000348e0:  mvn        r2, #0
  000348e4:  strb       r2, [r3, #0x9b]
  000348e8:  ldr        r3, [fp, #-0x1c]
  000348ec:  mvn        r2, #0
  000348f0:  strb       r2, [r3, #0x93]
  000348f4:  ldr        r3, [fp, #-0x1c]
  000348f8:  mvn        r2, #0
  000348fc:  strb       r2, [r3, #0x9c]
  00034900:  ldr        r3, [fp, #-0x1c]
  00034904:  mvn        r2, #0
  00034908:  strb       r2, [r3, #0x94]
  0003490c:  ldr        r3, [fp, #-0x1c]
  00034910:  mvn        r2, #0
  00034914:  strb       r2, [r3, #0x9d]
  00034918:  ldr        r3, [fp, #-0x1c]
  0003491c:  mvn        r2, #0
  00034920:  strb       r2, [r3, #0x95]
  00034924:  ldr        r3, [fp, #-0x1c]
  00034928:  mvn        r2, #0
  0003492c:  strb       r2, [r3, #0x9e]
  00034930:  ldr        r3, [fp, #-0x1c]
  00034934:  mvn        r2, #0
  00034938:  strb       r2, [r3, #0x96]
  0003493c:  ldr        r3, [fp, #-0x1c]
  00034940:  mvn        r2, #0
  00034944:  strb       r2, [r3, #0x9f]
  00034948:  ldr        r3, [fp, #-0x1c]
  0003494c:  mvn        r2, #0
  00034950:  strb       r2, [r3, #0x97]
  00034954:  ldr        r3, [fp, #-0x1c]
  00034958:  mvn        r2, #0
  0003495c:  strb       r2, [r3, #0xa0]
  00034960:  ldr        r3, [fp, #-0x1c]
  00034964:  mvn        r2, #0
  00034968:  strb       r2, [r3, #0x98]
  0003496c:  ldr        r3, [fp, #-0x1c]
  00034970:  mvn        r2, #0
  00034974:  strb       r2, [r3, #0xa1]
  00034978:  ldr        r3, [fp, #-0x1c]
  0003497c:  mov        r2, #1
  00034980:  strb       r2, [r3, #0xb4]
  00034984:  ldr        r3, [fp, #-0x18]
  00034988:  ldr        r3, [r3, #0x20]
  0003498c:  uxtb       r3, r3
  00034990:  and        r3, r3, #1
  00034994:  uxtb       r1, r3
  00034998:  ldr        r2, [fp, #-0x1c]
  0003499c:  ldrb       r3, [r2, #0x76]
  000349a0:  bfi        r3, r1, #5, #1
  000349a4:  strb       r3, [r2, #0x76]
  000349a8:  ldr        r3, [fp, #-0x18]
  000349ac:  ldr        r3, [r3, #0x20]
  000349b0:  uxtb       r3, r3
  000349b4:  and        r3, r3, #1
  000349b8:  uxtb       r1, r3
  000349bc:  ldr        r2, [fp, #-0x1c]
  000349c0:  ldrb       r3, [r2, #0x77]
  000349c4:  bfi        r3, r1, #1, #1
  000349c8:  strb       r3, [r2, #0x77]
  000349cc:  ldr        r3, [fp, #-0x18]
  000349d0:  ldr        r3, [r3, #0x1c]
  000349d4:  uxtb       r3, r3
  000349d8:  and        r3, r3, #1
  000349dc:  uxtb       r1, r3
  000349e0:  ldr        r2, [fp, #-0x1c]
  000349e4:  ldrb       r3, [r2, #0x76]
  000349e8:  bfi        r3, r1, #4, #1
  000349ec:  strb       r3, [r2, #0x76]
  000349f0:  ldr        r3, [fp, #-0x18]
  000349f4:  ldr        r3, [r3, #0x1c]
  000349f8:  uxtb       r3, r3
  000349fc:  and        r3, r3, #1
  00034a00:  uxtb       r1, r3
  00034a04:  ldr        r2, [fp, #-0x1c]
  00034a08:  ldrb       r3, [r2, #0x77]
  00034a0c:  bfi        r3, r1, #0, #1
  00034a10:  strb       r3, [r2, #0x77]
  00034a14:  ldr        r3, [fp, #-0x18]
  00034a18:  ldr        r2, [r3, #0x24]
  00034a1c:  movw       r3, #0x420b
  00034a20:  cmp        r2, r3
  00034a24:  bne        #0x34a68
  00034a28:  ldr        r2, [fp, #-0x1c]
  00034a2c:  ldrb       r3, [r2, #0x14]
  00034a30:  mov        r1, #5
  00034a34:  bfi        r3, r1, #0, #6
  00034a38:  strb       r3, [r2, #0x14]
  00034a3c:  ldr        r3, [fp, #-0x1c]
  00034a40:  ldrb       r3, [r3, #0x14]
  00034a44:  ubfx       r3, r3, #0, #6
  00034a48:  uxtb       r3, r3
  00034a4c:  str        r3, [fp, #-0x14]
  00034a50:  ldr        r2, [fp, #-0x1c]
  00034a54:  ldrb       r3, [r2, #0x49]
  00034a58:  mov        r1, #3
  00034a5c:  bfi        r3, r1, #0, #4
  00034a60:  strb       r3, [r2, #0x49]
  00034a64:  b          #0x34aa4
  00034a68:  ldr        r3, [fp, #-0x18]
  00034a6c:  ldr        r2, [r3, #0x24]
  00034a70:  movw       r3, #0x3202
  00034a74:  cmp        r2, r3
  00034a78:  bne        #0x34aa4
  00034a7c:  ldr        r2, [fp, #-0x1c]
  00034a80:  ldrb       r3, [r2, #0x14]
  00034a84:  mov        r1, #7
  00034a88:  bfi        r3, r1, #0, #6
  00034a8c:  strb       r3, [r2, #0x14]
  00034a90:  ldr        r3, [fp, #-0x1c]
  00034a94:  ldrb       r3, [r3, #0x14]
  00034a98:  ubfx       r3, r3, #0, #6
  00034a9c:  uxtb       r3, r3
  00034aa0:  str        r3, [fp, #-0x14]
  00034aa4:  ldr        r3, [fp, #-0x18]
  00034aa8:  ldr        r3, [r3, #0x28]
  00034aac:  cmp        r3, #1
  00034ab0:  beq        #0x34ad8
  00034ab4:  ldr        r3, [fp, #-0x18]
  00034ab8:  ldr        r3, [r3, #0x24]
  00034abc:  asr        r3, r3, #0xc
  00034ac0:  ldr        r0, [fp, #-0x18]
  00034ac4:  ldr        r1, [fp, #-0x1c]
  00034ac8:  mov        r2, r3
  00034acc:  bl         #0x34604
  00034ad0:  str        r0, [fp, #-0x14]
  00034ad4:  b          #0x34b28
  00034ad8:  ldr        r2, [fp, #-0x1c]
  00034adc:  ldrb       r3, [r2, #5]
  00034ae0:  orr        r3, r3, #1
  00034ae4:  strb       r3, [r2, #5]
  00034ae8:  ldr        r2, [fp, #-0x1c]
  00034aec:  ldrb       r3, [r2, #5]
  00034af0:  orr        r3, r3, #2
  00034af4:  strb       r3, [r2, #5]
  00034af8:  ldr        r2, [fp, #-0x1c]
  00034afc:  ldrb       r3, [r2, #5]
  00034b00:  orr        r3, r3, #4
  00034b04:  strb       r3, [r2, #5]
  00034b08:  ldr        r2, [fp, #-0x1c]
  00034b0c:  ldrb       r3, [r2, #5]
  00034b10:  orr        r3, r3, #8
  00034b14:  strb       r3, [r2, #5]
  00034b18:  ldr        r2, [fp, #-0x1c]
  00034b1c:  ldrb       r3, [r2, #5]
  00034b20:  orr        r3, r3, #0x10
  00034b24:  strb       r3, [r2, #5]
  00034b28:  ldr        r3, [fp, #-0x14]
  00034b2c:  uxtb       r3, r3
  00034b30:  and        r3, r3, #0x3f
  00034b34:  uxtb       r1, r3
  00034b38:  ldr        r2, [fp, #-0x1c]
  00034b3c:  ldrb       r3, [r2, #0x14]
  00034b40:  bfi        r3, r1, #0, #6
  00034b44:  strb       r3, [r2, #0x14]
  00034b48:  mov        r0, #9
  00034b4c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034b50:  mov        r3, r0
  00034b54:  uxtb       r1, r3
  00034b58:  ldr        r2, [fp, #-0x1c]
  00034b5c:  ldrb       r3, [r2, #0x73]
  00034b60:  bfi        r3, r1, #0, #8
  00034b64:  strb       r3, [r2, #0x73]
  00034b68:  mov        r0, #0xa
  00034b6c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034b70:  mov        r3, r0
  00034b74:  uxtb       r1, r3
  00034b78:  ldr        r2, [fp, #-0x1c]
  00034b7c:  ldrb       r3, [r2, #0x6c]
  00034b80:  bfi        r3, r1, #0, #8
  00034b84:  strb       r3, [r2, #0x6c]
  00034b88:  mov        r0, #0xb
  00034b8c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034b90:  mov        r3, r0
  00034b94:  uxtb       r1, r3
  00034b98:  ldr        r2, [fp, #-0x1c]
  00034b9c:  ldrb       r3, [r2, #0x6d]
  00034ba0:  bfi        r3, r1, #0, #8
  00034ba4:  strb       r3, [r2, #0x6d]
  00034ba8:  mov        r0, #0xc
  00034bac:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034bb0:  mov        r3, r0
  00034bb4:  uxtb       r1, r3
  00034bb8:  ldr        r2, [fp, #-0x1c]
  00034bbc:  ldrb       r3, [r2, #0x6e]
  00034bc0:  bfi        r3, r1, #0, #8
  00034bc4:  strb       r3, [r2, #0x6e]
  00034bc8:  mov        r0, #0xd
  00034bcc:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034bd0:  mov        r3, r0
  00034bd4:  uxtb       r1, r3
  00034bd8:  ldr        r2, [fp, #-0x1c]
  00034bdc:  ldrb       r3, [r2, #0x6f]
  00034be0:  bfi        r3, r1, #0, #8
  00034be4:  strb       r3, [r2, #0x6f]
  00034be8:  mov        r0, #5
  00034bec:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034bf0:  mov        r3, r0
  00034bf4:  uxtb       r1, r3
  00034bf8:  ldr        r2, [fp, #-0x1c]
  00034bfc:  ldrb       r3, [r2, #0x68]
  00034c00:  bfi        r3, r1, #0, #8
  00034c04:  strb       r3, [r2, #0x68]
  00034c08:  mov        r0, #6
  00034c0c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034c10:  mov        r3, r0
  00034c14:  uxtb       r1, r3
  00034c18:  ldr        r2, [fp, #-0x1c]
  00034c1c:  ldrb       r3, [r2, #0x69]
  00034c20:  bfi        r3, r1, #0, #8
  00034c24:  strb       r3, [r2, #0x69]
  00034c28:  mov        r0, #7
  00034c2c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034c30:  mov        r3, r0
  00034c34:  uxtb       r1, r3
  00034c38:  ldr        r2, [fp, #-0x1c]
  00034c3c:  ldrb       r3, [r2, #0x6a]
  00034c40:  bfi        r3, r1, #0, #8
  00034c44:  strb       r3, [r2, #0x6a]
  00034c48:  mov        r0, #8
  00034c4c:  bl         #0x83cc   // ->@plt d5_ep_mc_get_default_config
  00034c50:  mov        r3, r0
  00034c54:  uxtb       r1, r3
  00034c58:  ldr        r2, [fp, #-0x1c]
  00034c5c:  ldrb       r3, [r2, #0x6b]
  00034c60:  bfi        r3, r1, #0, #8
  00034c64:  strb       r3, [r2, #0x6b]
  00034c68:  ldr        r3, [fp, #-0x1c]
  00034c6c:  add        r3, r3, #0x90
  00034c70:  mov        r0, r3
  00034c74:  bl         #0x33b04
  00034c78:  ldr        r3, [pc, #0x340]
  00034c7c:  ldr        r3, [r4, r3]
  00034c80:  ldr        r3, [r3]
  00034c84:  add        r3, r3, #0x100
  00034c88:  ldr        r2, [fp, #-0x1c]
  00034c8c:  ldr        r2, [r2]
  00034c90:  str        r2, [r3]
  00034c94:  ldr        r3, [pc, #0x324]
  00034c98:  ldr        r3, [r4, r3]
  00034c9c:  ldr        r3, [r3]
  00034ca0:  add        r3, r3, #0x104
  00034ca4:  ldr        r2, [fp, #-0x1c]
  00034ca8:  ldr        r2, [r2, #4]
  00034cac:  str        r2, [r3]
  00034cb0:  ldr        r3, [pc, #0x308]
  00034cb4:  ldr        r3, [r4, r3]
  00034cb8:  ldr        r3, [r3]
  00034cbc:  add        r3, r3, #0x108
  00034cc0:  ldr        r2, [fp, #-0x1c]
  00034cc4:  ldr        r2, [r2, #8]
  00034cc8:  str        r2, [r3]
  00034ccc:  ldr        r3, [pc, #0x2ec]
  00034cd0:  ldr        r3, [r4, r3]
  00034cd4:  ldr        r3, [r3]
  00034cd8:  add        r3, r3, #0x68
  00034cdc:  ldr        r2, [fp, #-0x1c]
  00034ce0:  ldr        r2, [r2, #0xc]
  00034ce4:  str        r2, [r3]
  00034ce8:  ldr        r3, [pc, #0x2d0]
  00034cec:  ldr        r3, [r4, r3]
  00034cf0:  ldr        r3, [r3]
  00034cf4:  add        r3, r3, #0x6c
  00034cf8:  ldr        r2, [fp, #-0x1c]
  00034cfc:  ldr        r2, [r2, #0x10]
  00034d00:  str        r2, [r3]
  00034d04:  ldr        r3, [pc, #0x2b4]
  00034d08:  ldr        r3, [r4, r3]
  00034d0c:  ldr        r3, [r3]
  00034d10:  ldr        r2, [fp, #-0x1c]
  00034d14:  ldr        r2, [r2, #0x14]
  00034d18:  str        r2, [r3]
  00034d1c:  ldr        r3, [pc, #0x29c]
  00034d20:  ldr        r3, [r4, r3]
  00034d24:  ldr        r3, [r3]
  00034d28:  add        r3, r3, #0x64
  00034d2c:  ldr        r2, [fp, #-0x1c]
  00034d30:  ldr        r2, [r2, #0x18]
  00034d34:  str        r2, [r3]
  00034d38:  ldr        r3, [pc, #0x280]
  00034d3c:  ldr        r3, [r4, r3]
  00034d40:  ldr        r3, [r3]
  00034d44:  add        r3, r3, #8
  00034d48:  ldr        r2, [fp, #-0x1c]
  00034d4c:  ldr        r2, [r2, #0x1c]
  00034d50:  str        r2, [r3]
  00034d54:  ldr        r3, [pc, #0x264]
  00034d58:  ldr        r3, [r4, r3]
  00034d5c:  ldr        r3, [r3]
  00034d60:  add        r3, r3, #0xc
  00034d64:  ldr        r2, [fp, #-0x1c]
  00034d68:  ldr        r2, [r2, #0x20]
  00034d6c:  str        r2, [r3]
  00034d70:  ldr        r3, [pc, #0x248]
  00034d74:  ldr        r3, [r4, r3]
  00034d78:  ldr        r3, [r3]
  00034d7c:  add        r3, r3, #4
  00034d80:  ldr        r2, [fp, #-0x1c]
  00034d84:  ldr        r2, [r2, #0x34]
  00034d88:  str        r2, [r3]
  00034d8c:  mov        r3, #0
  00034d90:  str        r3, [fp, #-0x10]
  00034d94:  b          #0x34dd8
  00034d98:  ldr        r3, [fp, #-0x10]
  00034d9c:  lsl        r3, r3, #2
  00034da0:  mov        r2, r3
  00034da4:  ldr        r3, [pc, #0x214]
  00034da8:  ldr        r3, [r4, r3]
  00034dac:  ldr        r3, [r3]
  00034db0:  add        r3, r2, r3
  00034db4:  add        r3, r3, #0x20
  00034db8:  ldr        r2, [fp, #-0x1c]
  00034dbc:  ldr        r1, [fp, #-0x10]
  00034dc0:  add        r1, r1, #0xe
  00034dc4:  ldr        r2, [r2, r1, lsl #2]
  00034dc8:  str        r2, [r3]
  00034dcc:  ldr        r3, [fp, #-0x10]
  00034dd0:  add        r3, r3, #1
  00034dd4:  str        r3, [fp, #-0x10]
  00034dd8:  ldr        r3, [fp, #-0x10]
  00034ddc:  cmp        r3, #4
  00034de0:  bls        #0x34d98
  00034de4:  ldr        r3, [pc, #0x1d4]
  00034de8:  ldr        r3, [r4, r3]
  00034dec:  ldr        r3, [r3]
  00034df0:  add        r3, r3, #0x5c
  00034df4:  ldr        r2, [fp, #-0x1c]
  00034df8:  ldr        r2, [r2, #0x60]
  00034dfc:  str        r2, [r3]
  00034e00:  ldr        r3, [pc, #0x1b8]
  00034e04:  ldr        r3, [r4, r3]
  00034e08:  ldr        r3, [r3]
  00034e0c:  add        r3, r3, #0x60
  00034e10:  ldr        r2, [fp, #-0x1c]
  00034e14:  ldr        r2, [r2, #0x64]
  00034e18:  str        r2, [r3]
  00034e1c:  ldr        r3, [pc, #0x19c]
  00034e20:  ldr        r3, [r4, r3]
  00034e24:  ldr        r3, [r3]
  00034e28:  add        r3, r3, #0x11c
  00034e2c:  ldr        r2, [fp, #-0x1c]
  00034e30:  ldr        r2, [r2, #0x4c]
  00034e34:  str        r2, [r3]
  00034e38:  ldr        r3, [pc, #0x180]
  00034e3c:  ldr        r3, [r4, r3]
  00034e40:  ldr        r3, [r3]
  00034e44:  add        r3, r3, #0x120
  00034e48:  ldr        r2, [fp, #-0x1c]
  00034e4c:  ldr        r2, [r2, #0x50]
  00034e50:  str        r2, [r3]
  00034e54:  ldr        r3, [pc, #0x164]
  00034e58:  ldr        r3, [r4, r3]
  00034e5c:  ldr        r3, [r3]
  00034e60:  add        r3, r3, #0x124
  00034e64:  ldr        r2, [fp, #-0x1c]
  00034e68:  ldr        r2, [r2, #0x54]
  00034e6c:  str        r2, [r3]
  00034e70:  ldr        r3, [pc, #0x148]
  00034e74:  ldr        r3, [r4, r3]
  00034e78:  ldr        r3, [r3]
  00034e7c:  add        r3, r3, #0x128
  00034e80:  ldr        r2, [fp, #-0x1c]
  00034e84:  ldr        r2, [r2, #0x58]
  00034e88:  str        r2, [r3]
  00034e8c:  ldr        r3, [pc, #0x12c]
  00034e90:  ldr        r3, [r4, r3]
  00034e94:  ldr        r3, [r3]
  00034e98:  add        r3, r3, #0x12c

/* ===== _udd_ep_mc_rpath2_ctrl @ 0x0003a6d8  size=268  ARM ===== */
  0003a6d8:  push       {r4, fp, lr}
  0003a6dc:  add        fp, sp, #8
  0003a6e0:  sub        sp, sp, #0xcc
  0003a6e4:  str        r0, [fp, #-0xd0]
  0003a6e8:  str        r1, [fp, #-0xd4]
  0003a6ec:  ldr        r4, [pc, #0xe4]
  0003a6f0:  add        r4, pc, r4
  0003a6f4:  sub        r2, fp, #0xc8
  0003a6f8:  mov        r3, #0xb8
  0003a6fc:  mov        r0, r2
  0003a700:  mov        r1, #0
  0003a704:  mov        r2, r3
  0003a708:  bl         #0x8984   // ->@plt memset
  0003a70c:  mov        r3, #0x13
  0003a710:  str        r3, [fp, #-0x10]
  0003a714:  ldr        r3, [fp, #-0xd0]
  0003a718:  ldr        r3, [r3, #0x24]
  0003a71c:  uxtb       r3, r3
  0003a720:  cmp        r3, #0
  0003a724:  beq        #0x3a740
  0003a728:  ldr        r3, [fp, #-0xd0]
  0003a72c:  ldr        r3, [r3, #0x24]
  0003a730:  uxtb       r2, r3
  0003a734:  ldr        r3, [fp, #-0x10]
  0003a738:  cmp        r2, r3
  0003a73c:  blt        #0x3a74c
  0003a740:  movw       r3, #0xfe08
  0003a744:  movt       r3, #0xffff
  0003a748:  b          #0x3a7cc
  0003a74c:  sub        r3, fp, #0xc8
  0003a750:  ldr        r0, [fp, #-0xd0]
  0003a754:  mov        r1, r3
  0003a758:  ldr        r2, [fp, #-0xd4]
  0003a75c:  bl         #0x8ac8   // ->@plt _udd_ep_mc_ring_size_set
  0003a760:  ldr        r3, [pc, #0x74]
  0003a764:  ldr        r3, [r4, r3]
  0003a768:  ldr        r3, [r3]
  0003a76c:  add        r3, r3, #0x7c
  0003a770:  mov        r2, #0
  0003a774:  str        r2, [r3]
  0003a778:  ldrb       r3, [fp, #-0xb1]
  0003a77c:  orr        r3, r3, #0x10
  0003a780:  strb       r3, [fp, #-0xb1]
  0003a784:  ldrb       r3, [fp, #-0xb1]
  0003a788:  orr        r3, r3, #0x20
  0003a78c:  strb       r3, [fp, #-0xb1]
  0003a790:  ldr        r3, [fp, #-0xd0]
  0003a794:  ldr        r3, [r3, #0x24]
  0003a798:  uxtb       r2, r3
  0003a79c:  ldr        r3, [pc, #0x3c]
  0003a7a0:  add        r3, pc, r3
  0003a7a4:  ldr        r3, [r3, r2, lsl #2]
  0003a7a8:  sub        r2, fp, #0xc8
  0003a7ac:  mov        r0, r2
  0003a7b0:  ldr        r1, [fp, #-0xd4]
  0003a7b4:  blx        r3
  0003a7b8:  sub        r3, fp, #0xc8
  0003a7bc:  ldr        r0, [fp, #-0xd0]
  0003a7c0:  mov        r1, r3
  0003a7c4:  bl         #0x8e70   // ->@plt _udd_ep_mc_common_reg_set
  0003a7c8:  mov        r3, r0
  0003a7cc:  mov        r0, r3
  0003a7d0:  sub        sp, fp, #8
  0003a7d4:  pop        {r4, fp, pc}
  0003a7d8:  andeq      pc, r0, r8, asr #23
  0003a7dc:  andeq      r0, r0, r0, ror #10
  0003a7e0:  andeq      r0, r1, r0, lsr #30

/* ===== _udd_ep_mc_get_default_param4 @ 0x0003bb70  size=72  ARM ===== */
  0003bb70:  push       {fp, lr}
  0003bb74:  add        fp, sp, #4
  0003bb78:  sub        sp, sp, #8
  0003bb7c:  str        r0, [fp, #-8]
  0003bb80:  str        r1, [fp, #-0xc]
  0003bb84:  ldr        r3, [fp, #-8]
  0003bb88:  uxtb       r2, r3
  0003bb8c:  ldr        r3, [pc, #0x20]
  0003bb90:  add        r3, pc, r3
  0003bb94:  ldr        r3, [r3, r2, lsl #2]
  0003bb98:  ldr        r0, [fp, #-8]
  0003bb9c:  ldr        r1, [fp, #-0xc]
  0003bba0:  blx        r3
  0003bba4:  mov        r3, #0
  0003bba8:  mov        r0, r3
  0003bbac:  sub        sp, fp, #4
  0003bbb0:  pop        {fp, pc}
  0003bbb4:  .byte      0xf4, 0xff, 0x00, 0x00

