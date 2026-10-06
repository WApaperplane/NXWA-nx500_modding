/* ===== d5_ep_3dlut_op_init @ 0x00019080  size=228  ARM ===== */
  00019080:  push       {fp, lr}
  00019084:  add        fp, sp, #4
  00019088:  sub        sp, sp, #0x30
  0001908c:  str        r0, [fp, #-0x30]
  00019090:  mov        r3, #0
  00019094:  str        r3, [fp, #-8]
  00019098:  ldr        r3, [fp, #-0x30]
  0001909c:  cmp        r3, #0
  000190a0:  bne        #0x190ac
  000190a4:  mvn        r3, #0
  000190a8:  b          #0x19158
  000190ac:  ldr        r3, [fp, #-0x30]
  000190b0:  ldr        r3, [r3, #0xc]
  000190b4:  cmp        r3, #1
  000190b8:  bne        #0x190d8
  000190bc:  mov        r3, #0
  000190c0:  str        r3, [fp, #-0x2c]
  000190c4:  sub        r3, fp, #0x2c
  000190c8:  mov        r0, r3
  000190cc:  bl         #0x88f4   // ->@plt _udd_ep_3dl_ctrl_ConfigBypassMode
  000190d0:  str        r0, [fp, #-8]
  000190d4:  b          #0x19154
  000190d8:  ldr        r3, [fp, #-0x30]
  000190dc:  ldr        r3, [r3, #8]
  000190e0:  cmp        r3, #2
  000190e4:  bls        #0x190f0
  000190e8:  mvn        r3, #0
  000190ec:  b          #0x19158
  000190f0:  ldr        r3, [fp, #-0x30]
  000190f4:  ldr        r3, [r3]
  000190f8:  cmp        r3, #0
  000190fc:  beq        #0x19118
  00019100:  ldr        r3, [fp, #-0x30]
  00019104:  ldr        r3, [r3]
  00019108:  cmp        r3, #1
  0001910c:  beq        #0x19118
  00019110:  mvn        r3, #0
  00019114:  b          #0x19158
  00019118:  mov        r3, #2
  0001911c:  str        r3, [fp, #-0x2c]
  00019120:  ldr        r3, [fp, #-0x30]
  00019124:  ldr        r3, [r3, #4]
  00019128:  str        r3, [fp, #-0x18]
  0001912c:  ldr        r3, [fp, #-0x30]
  00019130:  ldr        r3, [r3]
  00019134:  str        r3, [fp, #-0x14]
  00019138:  ldr        r3, [fp, #-0x30]
  0001913c:  ldr        r3, [r3, #8]
  00019140:  str        r3, [fp, #-0x1c]
  00019144:  sub        r3, fp, #0x2c
  00019148:  mov        r0, r3
  0001914c:  bl         #0x8264   // ->@plt _udd_ep_3dl_ctrl_ConfigProcessMode
  00019150:  str        r0, [fp, #-8]
  00019154:  ldr        r3, [fp, #-8]
  00019158:  mov        r0, r3
  0001915c:  sub        sp, fp, #4
  00019160:  pop        {fp, pc}

/* ===== d5_ep_3dl_load_lut @ 0x00019164  size=260  ARM ===== */
  00019164:  push       {fp, lr}
  00019168:  add        fp, sp, #4
  0001916c:  sub        sp, sp, #0x48
  00019170:  str        r0, [fp, #-0x40]
  00019174:  str        r1, [fp, #-0x44]
  00019178:  str        r2, [fp, #-0x48]
  0001917c:  str        r3, [fp, #-0x4c]
  00019180:  ldr        r3, [fp, #-0x40]
  00019184:  mov        r0, r3
  00019188:  bl         #0x8930   // ->@plt d5_ep_sma_virt_to_phys
  0001918c:  str        r0, [fp, #-8]
  00019190:  mov        r3, #0
  00019194:  str        r3, [fp, #-0xc]
  00019198:  ldr        r3, [fp, #-0x40]
  0001919c:  cmp        r3, #0
  000191a0:  bne        #0x191ac
  000191a4:  mvn        r3, #0
  000191a8:  b          #0x1925c
  000191ac:  ldr        r3, [fp, #-0x44]
  000191b0:  cmp        r3, #2
  000191b4:  bls        #0x191c0
  000191b8:  mvn        r3, #0
  000191bc:  b          #0x1925c
  000191c0:  ldr        r3, [fp, #-0x48]
  000191c4:  cmp        r3, #0
  000191c8:  beq        #0x191e0
  000191cc:  ldr        r3, [fp, #-0x48]
  000191d0:  cmp        r3, #1
  000191d4:  beq        #0x191e0
  000191d8:  mvn        r3, #0
  000191dc:  b          #0x1925c
  000191e0:  mov        r3, #1
  000191e4:  str        r3, [fp, #-0x30]
  000191e8:  mov        r3, #1
  000191ec:  str        r3, [fp, #-0x2c]
  000191f0:  ldr        r3, [fp, #-0x44]
  000191f4:  str        r3, [fp, #-0x20]
  000191f8:  ldr        r3, [fp, #-0x44]
  000191fc:  cmp        r3, #0
  00019200:  bne        #0x19228
  00019204:  sub        r3, fp, #0x3c
  00019208:  str        r3, [fp, #-0x28]
  0001920c:  ldr        r3, [fp, #-0x28]
  00019210:  ldr        r2, [fp, #-8]
  00019214:  str        r2, [r3]
  00019218:  ldr        r3, [fp, #-0x28]
  0001921c:  ldr        r2, [fp, #-0x48]
  00019220:  str        r2, [r3, #8]
  00019224:  b          #0x19248
  00019228:  sub        r3, fp, #0x3c
  0001922c:  str        r3, [fp, #-0x24]
  00019230:  ldr        r3, [fp, #-0x24]
  00019234:  ldr        r2, [fp, #-8]
  00019238:  str        r2, [r3]
  0001923c:  ldr        r3, [fp, #-0x24]
  00019240:  ldr        r2, [fp, #-0x48]
  00019244:  str        r2, [r3, #8]
  00019248:  sub        r3, fp, #0x30
  0001924c:  mov        r0, r3
  00019250:  bl         #0x84e0   // ->@plt _udd_ep_3dl_ctrl_ConfigAccessMode
  00019254:  str        r0, [fp, #-0xc]
  00019258:  ldr        r3, [fp, #-0xc]
  0001925c:  mov        r0, r3
  00019260:  sub        sp, fp, #4
  00019264:  pop        {fp, pc}

/* ===== d5_ep_3dl_save_lut @ 0x00019268  size=276  ARM ===== */
  00019268:  push       {fp, lr}
  0001926c:  add        fp, sp, #4
  00019270:  sub        sp, sp, #0x48
  00019274:  str        r0, [fp, #-0x40]
  00019278:  str        r1, [fp, #-0x44]
  0001927c:  str        r2, [fp, #-0x48]
  00019280:  str        r3, [fp, #-0x4c]
  00019284:  ldr        r3, [fp, #-0x40]
  00019288:  mov        r0, r3
  0001928c:  bl         #0x8930   // ->@plt d5_ep_sma_virt_to_phys
  00019290:  str        r0, [fp, #-8]
  00019294:  ldr        r3, [fp, #-0x40]
  00019298:  cmp        r3, #0
  0001929c:  bne        #0x192a8
  000192a0:  mvn        r3, #0
  000192a4:  b          #0x19370
  000192a8:  ldr        r3, [fp, #-8]
  000192ac:  uxtb       r3, r3
  000192b0:  cmp        r3, #0
  000192b4:  beq        #0x192c0
  000192b8:  mvn        r3, #0x12c
  000192bc:  b          #0x19370
  000192c0:  ldr        r3, [fp, #-0x44]
  000192c4:  cmp        r3, #2
  000192c8:  bls        #0x192d4
  000192cc:  mvn        r3, #0
  000192d0:  b          #0x19370
  000192d4:  ldr        r3, [fp, #-0x48]
  000192d8:  cmp        r3, #0
  000192dc:  beq        #0x192f4
  000192e0:  ldr        r3, [fp, #-0x48]
  000192e4:  cmp        r3, #1
  000192e8:  beq        #0x192f4
  000192ec:  mvn        r3, #0
  000192f0:  b          #0x19370
  000192f4:  mov        r3, #1
  000192f8:  str        r3, [fp, #-0x30]
  000192fc:  mov        r3, #2
  00019300:  str        r3, [fp, #-0x2c]
  00019304:  ldr        r3, [fp, #-0x44]
  00019308:  str        r3, [fp, #-0x20]
  0001930c:  ldr        r3, [fp, #-0x44]
  00019310:  cmp        r3, #0
  00019314:  bne        #0x1933c
  00019318:  sub        r3, fp, #0x3c
  0001931c:  str        r3, [fp, #-0x28]
  00019320:  ldr        r3, [fp, #-0x28]
  00019324:  ldr        r2, [fp, #-8]
  00019328:  str        r2, [r3, #4]
  0001932c:  ldr        r3, [fp, #-0x28]
  00019330:  ldr        r2, [fp, #-0x48]
  00019334:  str        r2, [r3, #8]
  00019338:  b          #0x1935c
  0001933c:  sub        r3, fp, #0x3c
  00019340:  str        r3, [fp, #-0x24]
  00019344:  ldr        r3, [fp, #-0x24]
  00019348:  ldr        r2, [fp, #-8]
  0001934c:  str        r2, [r3, #4]
  00019350:  ldr        r3, [fp, #-0x24]
  00019354:  ldr        r2, [fp, #-0x48]
  00019358:  str        r2, [r3, #8]
  0001935c:  sub        r3, fp, #0x30
  00019360:  mov        r0, r3
  00019364:  bl         #0x84e0   // ->@plt _udd_ep_3dl_ctrl_ConfigAccessMode
  00019368:  str        r0, [fp, #-0xc]
  0001936c:  ldr        r3, [fp, #-0xc]
  00019370:  mov        r0, r3
  00019374:  sub        sp, fp, #4
  00019378:  pop        {fp, pc}

/* ===== _udd_ep_mux_3dlut_rdxi @ 0x0001b5b8  size=564  ARM ===== */
  0001b5b8:  push       {r4, fp, lr}
  0001b5bc:  add        fp, sp, #8
  0001b5c0:  sub        sp, sp, #0x1c
  0001b5c4:  str        r0, [fp, #-0x20]
  0001b5c8:  str        r1, [fp, #-0x24]
  0001b5cc:  ldr        r4, [pc, #0x1f8]
  0001b5d0:  add        r4, pc, r4
  0001b5d4:  mvn        r3, #0
  0001b5d8:  str        r3, [fp, #-0x10]
  0001b5dc:  ldr        r3, [fp, #-0x24]
  0001b5e0:  cmp        r3, #0
  0001b5e4:  bne        #0x1b5f0
  0001b5e8:  movw       r3, #0x1104
  0001b5ec:  b          #0x1b5f4
  0001b5f0:  movw       r3, #0x1204
  0001b5f4:  str        r3, [fp, #-0x14]
  0001b5f8:  ldr        r3, [pc, #0x1d0]
  0001b5fc:  ldr        r3, [r4, r3]
  0001b600:  ldr        r2, [r3]
  0001b604:  ldr        r3, [fp, #-0x14]
  0001b608:  add        r3, r2, r3
  0001b60c:  ldr        r3, [r3]
  0001b610:  str        r3, [fp, #-0x18]
  0001b614:  ldr        r3, [fp, #-0x20]
  0001b618:  cmp        r3, #0x10
  0001b61c:  bhi        #0x1b774
  0001b620:  mov        r2, #1
  0001b624:  ldr        r3, [fp, #-0x20]
  0001b628:  lsl        r3, r2, r3
  0001b62c:  movw       r2, #0x436
  0001b630:  and        r2, r3, r2
  0001b634:  cmp        r2, #0
  0001b638:  bne        #0x1b658
  0001b63c:  and        r2, r3, #0x10000
  0001b640:  cmp        r2, #0
  0001b644:  bne        #0x1b708
  0001b648:  and        r3, r3, #0x3c0
  0001b64c:  cmp        r3, #0
  0001b650:  bne        #0x1b680
  0001b654:  b          #0x1b774
  0001b658:  ldr        r3, [fp, #-0x20]
  0001b65c:  uxtb       r3, r3
  0001b660:  and        r3, r3, #0xf
  0001b664:  uxtb       r2, r3
  0001b668:  ldr        r3, [fp, #-0x18]
  0001b66c:  bfi        r3, r2, #4, #4
  0001b670:  str        r3, [fp, #-0x18]
  0001b674:  mov        r3, #0xa
  0001b678:  str        r3, [fp, #-0x10]
  0001b67c:  b          #0x1b7a0
  0001b680:  ldr        r3, [fp, #-0x20]
  0001b684:  sub        r3, r3, #6
  0001b688:  mov        r0, r3
  0001b68c:  ldr        r1, [fp, #-0x24]
  0001b690:  bl         #0x8348   // ->@plt _udd_ep_rdma_check_empty
  0001b694:  mov        r3, r0
  0001b698:  cmp        r3, #0
  0001b69c:  beq        #0x1b6cc
  0001b6a0:  ldr        r3, [fp, #-0x20]
  0001b6a4:  uxtb       r3, r3
  0001b6a8:  and        r3, r3, #0xf
  0001b6ac:  uxtb       r2, r3
  0001b6b0:  ldr        r3, [fp, #-0x18]
  0001b6b4:  bfi        r3, r2, #4, #4
  0001b6b8:  str        r3, [fp, #-0x18]
  0001b6bc:  ldr        r3, [fp, #-0x20]
  0001b6c0:  sub        r3, r3, #6
  0001b6c4:  str        r3, [fp, #-0x10]
  0001b6c8:  b          #0x1b7a0
  0001b6cc:  ldr        r3, [pc, #0x100]
  0001b6d0:  add        r3, pc, r3
  0001b6d4:  mov        r2, r3
  0001b6d8:  ldr        r3, [fp, #-0x20]
  0001b6dc:  sub        r3, r3, #6
  0001b6e0:  mov        r0, r2
  0001b6e4:  mov        r1, r3
  0001b6e8:  ldr        r3, [pc, #0xe8]
  0001b6ec:  add        r3, pc, r3
  0001b6f0:  mov        r2, r3
  0001b6f4:  mov        r3, #0xcb
  0001b6f8:  bl         #0x8258   // ->@plt printf
  0001b6fc:  mvn        r3, #0
  0001b700:  str        r3, [fp, #-0x10]
  0001b704:  b          #0x1b7a0
  0001b708:  ldr        r0, [fp, #-0x24]
  0001b70c:  bl         #0x89d8   // ->@plt _udd_ep_rdma_get_empty
  0001b710:  str        r0, [fp, #-0x10]
  0001b714:  ldr        r3, [fp, #-0x10]
  0001b718:  cmn        r3, #1
  0001b71c:  beq        #0x1b748
  0001b720:  ldr        r3, [fp, #-0x10]
  0001b724:  uxtb       r3, r3
  0001b728:  add        r3, r3, #6
  0001b72c:  uxtb       r3, r3
  0001b730:  and        r3, r3, #0xf
  0001b734:  uxtb       r2, r3
  0001b738:  ldr        r3, [fp, #-0x18]
  0001b73c:  bfi        r3, r2, #4, #4
  0001b740:  str        r3, [fp, #-0x18]
  0001b744:  b          #0x1b7a0
  0001b748:  ldr        r3, [pc, #0x8c]
  0001b74c:  add        r3, pc, r3
  0001b750:  mov        r0, r3
  0001b754:  ldr        r3, [pc, #0x84]
  0001b758:  add        r3, pc, r3
  0001b75c:  mov        r1, r3
  0001b760:  mov        r2, #0xd5
  0001b764:  bl         #0x8258   // ->@plt printf
  0001b768:  mvn        r3, #0
  0001b76c:  str        r3, [fp, #-0x10]
  0001b770:  b          #0x1b7a0
  0001b774:  ldr        r3, [pc, #0x68]
  0001b778:  add        r3, pc, r3
  0001b77c:  mov        r0, r3
  0001b780:  ldr        r3, [pc, #0x60]
  0001b784:  add        r3, pc, r3
  0001b788:  mov        r1, r3
  0001b78c:  mov        r2, #0xdc
  0001b790:  bl         #0x8258   // ->@plt printf
  0001b794:  mvn        r3, #0
  0001b798:  str        r3, [fp, #-0x10]
  0001b79c:  mov        r0, r0
  0001b7a0:  ldr        r3, [pc, #0x28]
  0001b7a4:  ldr        r3, [r4, r3]
  0001b7a8:  ldr        r2, [r3]
  0001b7ac:  ldr        r3, [fp, #-0x14]
  0001b7b0:  add        r3, r2, r3
  0001b7b4:  ldr        r2, [fp, #-0x18]
  0001b7b8:  str        r2, [r3]
  0001b7bc:  ldr        r3, [fp, #-0x10]
  0001b7c0:  mov        r0, r3
  0001b7c4:  sub        sp, fp, #8
  0001b7c8:  pop        {r4, fp, pc}
  0001b7cc:  andeq      lr, r2, r8, ror #25
  0001b7d0:  ldrdeq     r0, r1, [r0], -r4
  0001b7d4:  andeq      r5, r2, r0, lsl #26
  0001b7d8:  ldrdeq     r6, r7, [r2], -ip
  0001b7dc:  andeq      r5, r2, ip, asr #25
  0001b7e0:  andeq      r6, r2, r0, ror r0
  0001b7e4:  strheq     r5, [r2], -ip
  0001b7e8:  andeq      r6, r2, r4, asr #32

/* ===== _udd_ep_mux_3dlut_wdxi @ 0x0001c9d0  size=296  ARM ===== */
  0001c9d0:  push       {fp, lr}
  0001c9d4:  add        fp, sp, #4
  0001c9d8:  sub        sp, sp, #0x10
  0001c9dc:  str        r0, [fp, #-0x10]
  0001c9e0:  str        r1, [fp, #-0x14]
  0001c9e4:  mvn        r3, #0
  0001c9e8:  str        r3, [fp, #-8]
  0001c9ec:  ldr        r3, [fp, #-0x10]
  0001c9f0:  cmp        r3, #0
  0001c9f4:  blt        #0x1cacc
  0001c9f8:  cmp        r3, #4
  0001c9fc:  ble        #0x1ca0c
  0001ca00:  cmp        r3, #0x14
  0001ca04:  beq        #0x1ca70
  0001ca08:  b          #0x1cacc
  0001ca0c:  ldr        r0, [fp, #-0x10]
  0001ca10:  ldr        r1, [fp, #-0x14]
  0001ca14:  bl         #0x8bdc   // ->@plt _udd_ep_wdma_check_empty
  0001ca18:  mov        r3, r0
  0001ca1c:  cmp        r3, #0
  0001ca20:  beq        #0x1ca40
  0001ca24:  ldr        r0, [fp, #-0x10]
  0001ca28:  mov        r1, #3
  0001ca2c:  ldr        r2, [fp, #-0x14]
  0001ca30:  bl         #0x8e64   // ->@plt _udd_ep_mux_wdma
  0001ca34:  ldr        r3, [fp, #-0x10]
  0001ca38:  str        r3, [fp, #-8]
  0001ca3c:  b          #0x1cad8
  0001ca40:  ldr        r3, [pc, #0xa0]
  0001ca44:  add        r3, pc, r3
  0001ca48:  mov        r0, r3
  0001ca4c:  ldr        r1, [fp, #-0x10]
  0001ca50:  ldr        r3, [pc, #0x94]
  0001ca54:  add        r3, pc, r3
  0001ca58:  mov        r2, r3
  0001ca5c:  movw       r3, #0x2ae
  0001ca60:  bl         #0x8258   // ->@plt printf
  0001ca64:  mvn        r3, #0
  0001ca68:  str        r3, [fp, #-8]
  0001ca6c:  b          #0x1cad8
  0001ca70:  ldr        r0, [fp, #-0x14]
  0001ca74:  bl         #0x8d74   // ->@plt _udd_ep_wdma_get_empty
  0001ca78:  str        r0, [fp, #-8]
  0001ca7c:  ldr        r3, [fp, #-8]
  0001ca80:  cmn        r3, #1
  0001ca84:  beq        #0x1ca9c
  0001ca88:  ldr        r0, [fp, #-8]
  0001ca8c:  mov        r1, #3
  0001ca90:  ldr        r2, [fp, #-0x14]
  0001ca94:  bl         #0x8e64   // ->@plt _udd_ep_mux_wdma
  0001ca98:  b          #0x1cad8
  0001ca9c:  ldr        r3, [pc, #0x4c]
  0001caa0:  add        r3, pc, r3
  0001caa4:  mov        r0, r3
  0001caa8:  ldr        r1, [fp, #-0x10]
  0001caac:  ldr        r3, [pc, #0x40]
  0001cab0:  add        r3, pc, r3
  0001cab4:  mov        r2, r3
  0001cab8:  movw       r3, #0x2b7
  0001cabc:  bl         #0x8258   // ->@plt printf
  0001cac0:  mvn        r3, #0
  0001cac4:  str        r3, [fp, #-8]
  0001cac8:  b          #0x1cad8
  0001cacc:  mvn        r3, #0
  0001cad0:  str        r3, [fp, #-8]
  0001cad4:  mov        r0, r0
  0001cad8:  ldr        r3, [fp, #-8]
  0001cadc:  mov        r0, r3
  0001cae0:  sub        sp, fp, #4
  0001cae4:  pop        {fp, pc}
  0001cae8:  andeq      r4, r2, r8, lsr sl
  0001caec:  muleq      r2, ip, ip
  0001caf0:  ldrdeq     r4, r5, [r2], -ip
  0001caf4:  andeq      r4, r2, r0, asr #24

/* ===== _udd_ep_demux_3dlut_rdxi @ 0x0001d844  size=140  ARM ===== */
  0001d844:  str        fp, [sp, #-4]!
  0001d848:  add        fp, sp, #0
  0001d84c:  sub        sp, sp, #0x14
  0001d850:  str        r0, [fp, #-0x10]
  0001d854:  ldr        r2, [pc, #0x6c]
  0001d858:  add        r2, pc, r2
  0001d85c:  ldr        r3, [fp, #-0x10]
  0001d860:  cmp        r3, #0
  0001d864:  bne        #0x1d870
  0001d868:  movw       r3, #0x1104
  0001d86c:  b          #0x1d874
  0001d870:  movw       r3, #0x1204
  0001d874:  str        r3, [fp, #-8]
  0001d878:  ldr        r3, [pc, #0x4c]
  0001d87c:  ldr        r3, [r2, r3]
  0001d880:  ldr        r1, [r3]
  0001d884:  ldr        r3, [fp, #-8]
  0001d888:  add        r3, r1, r3
  0001d88c:  ldr        r3, [r3]
  0001d890:  str        r3, [fp, #-0xc]
  0001d894:  ldr        r3, [fp, #-0xc]
  0001d898:  orr        r3, r3, #0xf0
  0001d89c:  str        r3, [fp, #-0xc]
  0001d8a0:  ldr        r3, [pc, #0x24]
  0001d8a4:  ldr        r3, [r2, r3]
  0001d8a8:  ldr        r2, [r3]
  0001d8ac:  ldr        r3, [fp, #-8]
  0001d8b0:  add        r3, r2, r3
  0001d8b4:  ldr        r2, [fp, #-0xc]
  0001d8b8:  str        r2, [r3]
  0001d8bc:  add        sp, fp, #0
  0001d8c0:  ldm        sp!, {fp}
  0001d8c4:  bx         lr
  0001d8c8:  andeq      ip, r2, r0, ror #20
  0001d8cc:  ldrdeq     r0, r1, [r0], -r4

/* ===== _udd_ep_demux_3dlut_wdxi @ 0x0001ddc4  size=288  ARM ===== */
  0001ddc4:  str        fp, [sp, #-4]!
  0001ddc8:  add        fp, sp, #0
  0001ddcc:  sub        sp, sp, #0x1c
  0001ddd0:  str        r0, [fp, #-0x18]
  0001ddd4:  ldr        r3, [pc, #0x100]
  0001ddd8:  add        r3, pc, r3
  0001dddc:  ldr        r2, [fp, #-0x18]
  0001dde0:  cmp        r2, #0
  0001dde4:  bne        #0x1ddf0
  0001dde8:  movw       r2, #0x110c
  0001ddec:  b          #0x1ddf4
  0001ddf0:  movw       r2, #0x120c
  0001ddf4:  str        r2, [fp, #-0xc]
  0001ddf8:  ldr        r2, [pc, #0xe0]
  0001ddfc:  ldr        r2, [r3, r2]
  0001de00:  ldr        r1, [r2]
  0001de04:  ldr        r2, [fp, #-0xc]
  0001de08:  add        r2, r1, r2
  0001de0c:  ldr        r2, [r2]
  0001de10:  str        r2, [fp, #-0x14]
  0001de14:  mov        r2, #0
  0001de18:  str        r2, [fp, #-8]
  0001de1c:  b          #0x1de50
  0001de20:  ldr        r1, [fp, #-0x14]
  0001de24:  ldr        r2, [fp, #-8]
  0001de28:  lsl        r2, r2, #2
  0001de2c:  lsr        r2, r1, r2
  0001de30:  and        r2, r2, #0xf
  0001de34:  str        r2, [fp, #-0x10]
  0001de38:  ldr        r2, [fp, #-0x10]
  0001de3c:  cmp        r2, #3
  0001de40:  beq        #0x1de60
  0001de44:  ldr        r2, [fp, #-8]
  0001de48:  add        r2, r2, #1
  0001de4c:  str        r2, [fp, #-8]
  0001de50:  ldr        r2, [fp, #-8]
  0001de54:  cmp        r2, #4
  0001de58:  bls        #0x1de20
  0001de5c:  b          #0x1de64
  0001de60:  mov        r0, r0
  0001de64:  ldr        r2, [fp, #-8]
  0001de68:  cmp        r2, #5
  0001de6c:  beq        #0x1decc
  0001de70:  ldr        r1, [fp, #-0x14]
  0001de74:  ldr        r2, [fp, #-8]
  0001de78:  lsl        r2, r2, #2
  0001de7c:  mov        r0, #0xf
  0001de80:  lsl        r2, r0, r2
  0001de84:  mvn        r2, r2
  0001de88:  and        r2, r1, r2
  0001de8c:  str        r2, [fp, #-0x14]
  0001de90:  ldr        r1, [fp, #-0x14]
  0001de94:  ldr        r2, [fp, #-8]
  0001de98:  lsl        r2, r2, #2
  0001de9c:  mov        r0, #0xf
  0001dea0:  lsl        r2, r0, r2
  0001dea4:  orr        r2, r1, r2
  0001dea8:  str        r2, [fp, #-0x14]
  0001deac:  ldr        r2, [pc, #0x2c]
  0001deb0:  ldr        r3, [r3, r2]
  0001deb4:  ldr        r2, [r3]
  0001deb8:  ldr        r3, [fp, #-0xc]
  0001debc:  add        r3, r2, r3
  0001dec0:  ldr        r2, [fp, #-0x14]
  0001dec4:  str        r2, [r3]
  0001dec8:  b          #0x1ded0
  0001decc:  mov        r0, r0
  0001ded0:  add        sp, fp, #0
  0001ded4:  ldm        sp!, {fp}
  0001ded8:  bx         lr
  0001dedc:  andeq      ip, r2, r0, ror #9
  0001dee0:  ldrdeq     r0, r1, [r0], -r4

/* ===== _udd_ep_3dl_reg_GetReg @ 0x0001fa20  size=40  ARM ===== */
  0001fa20:  str        fp, [sp, #-4]!
  0001fa24:  add        fp, sp, #0
  0001fa28:  sub        sp, sp, #0xc
  0001fa2c:  str        r0, [fp, #-8]
  0001fa30:  ldr        r3, [fp, #-8]
  0001fa34:  ldr        r3, [r3]
  0001fa38:  mov        r0, r3
  0001fa3c:  add        sp, fp, #0
  0001fa40:  ldm        sp!, {fp}
  0001fa44:  bx         lr

/* ===== _udd_ep_3dl_reg_SetReg @ 0x0001fa48  size=44  ARM ===== */
  0001fa48:  str        fp, [sp, #-4]!
  0001fa4c:  add        fp, sp, #0
  0001fa50:  sub        sp, sp, #0xc
  0001fa54:  str        r0, [fp, #-8]
  0001fa58:  str        r1, [fp, #-0xc]
  0001fa5c:  ldr        r3, [fp, #-8]
  0001fa60:  ldr        r2, [fp, #-0xc]
  0001fa64:  str        r2, [r3]
  0001fa68:  add        sp, fp, #0
  0001fa6c:  ldm        sp!, {fp}
  0001fa70:  bx         lr

/* ===== _udd_ep_3dl_reg_OnOff @ 0x0001fa74  size=136  ARM ===== */
  0001fa74:  push       {r4, fp, lr}
  0001fa78:  add        fp, sp, #8
  0001fa7c:  sub        sp, sp, #0x14
  0001fa80:  str        r0, [fp, #-0x18]
  0001fa84:  ldr        r4, [pc, #0x68]
  0001fa88:  add        r4, pc, r4
  0001fa8c:  ldr        r3, [pc, #0x64]
  0001fa90:  ldr        r3, [r4, r3]
  0001fa94:  ldr        r3, [r3]
  0001fa98:  mov        r0, r3
  0001fa9c:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001faa0:  mov        r3, r0
  0001faa4:  str        r3, [fp, #-0x10]
  0001faa8:  ldr        r3, [fp, #-0x18]
  0001faac:  cmp        r3, #1
  0001fab0:  bne        #0x1fac4
  0001fab4:  ldr        r3, [fp, #-0x10]
  0001fab8:  orr        r3, r3, #1
  0001fabc:  str        r3, [fp, #-0x10]
  0001fac0:  b          #0x1fad0
  0001fac4:  ldr        r3, [fp, #-0x10]
  0001fac8:  bfc        r3, #0, #1
  0001facc:  str        r3, [fp, #-0x10]
  0001fad0:  ldr        r3, [pc, #0x20]
  0001fad4:  ldr        r3, [r4, r3]
  0001fad8:  ldr        r2, [r3]
  0001fadc:  ldr        r3, [fp, #-0x10]
  0001fae0:  mov        r0, r2
  0001fae4:  mov        r1, r3
  0001fae8:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001faec:  sub        sp, fp, #8
  0001faf0:  pop        {r4, fp, pc}
  0001faf4:  andeq      sl, r2, r0, lsr r8
  0001faf8:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_SelCbCr_ch @ 0x0001fafc  size=132  ARM ===== */
  0001fafc:  push       {r4, fp, lr}
  0001fb00:  add        fp, sp, #8
  0001fb04:  sub        sp, sp, #0x14
  0001fb08:  str        r0, [fp, #-0x18]
  0001fb0c:  ldr        r4, [pc, #0x64]
  0001fb10:  add        r4, pc, r4
  0001fb14:  ldr        r3, [pc, #0x60]
  0001fb18:  ldr        r3, [r4, r3]
  0001fb1c:  ldr        r3, [r3]
  0001fb20:  add        r3, r3, #4
  0001fb24:  mov        r0, r3
  0001fb28:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fb2c:  mov        r3, r0
  0001fb30:  str        r3, [fp, #-0x10]
  0001fb34:  ldr        r3, [fp, #-0x18]
  0001fb38:  uxtb       r3, r3
  0001fb3c:  and        r3, r3, #3
  0001fb40:  uxtb       r2, r3
  0001fb44:  ldr        r3, [fp, #-0x10]
  0001fb48:  bfi        r3, r2, #0, #2
  0001fb4c:  str        r3, [fp, #-0x10]
  0001fb50:  ldr        r3, [pc, #0x24]
  0001fb54:  ldr        r3, [r4, r3]
  0001fb58:  ldr        r3, [r3]
  0001fb5c:  add        r2, r3, #4
  0001fb60:  ldr        r3, [fp, #-0x10]
  0001fb64:  mov        r0, r2
  0001fb68:  mov        r1, r3
  0001fb6c:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fb70:  sub        sp, fp, #8
  0001fb74:  pop        {r4, fp, pc}
  0001fb78:  andeq      sl, r2, r8, lsr #15
  0001fb7c:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_SelLUT @ 0x0001fb80  size=132  ARM ===== */
  0001fb80:  push       {r4, fp, lr}
  0001fb84:  add        fp, sp, #8
  0001fb88:  sub        sp, sp, #0x14
  0001fb8c:  str        r0, [fp, #-0x18]
  0001fb90:  ldr        r4, [pc, #0x64]
  0001fb94:  add        r4, pc, r4
  0001fb98:  ldr        r3, [pc, #0x60]
  0001fb9c:  ldr        r3, [r4, r3]
  0001fba0:  ldr        r3, [r3]
  0001fba4:  add        r3, r3, #4
  0001fba8:  mov        r0, r3
  0001fbac:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fbb0:  mov        r3, r0
  0001fbb4:  str        r3, [fp, #-0x10]
  0001fbb8:  ldr        r3, [fp, #-0x18]
  0001fbbc:  uxtb       r3, r3
  0001fbc0:  and        r3, r3, #3
  0001fbc4:  uxtb       r2, r3
  0001fbc8:  ldr        r3, [fp, #-0x10]
  0001fbcc:  bfi        r3, r2, #4, #2
  0001fbd0:  str        r3, [fp, #-0x10]
  0001fbd4:  ldr        r3, [pc, #0x24]
  0001fbd8:  ldr        r3, [r4, r3]
  0001fbdc:  ldr        r3, [r3]
  0001fbe0:  add        r2, r3, #4
  0001fbe4:  ldr        r3, [fp, #-0x10]
  0001fbe8:  mov        r0, r2
  0001fbec:  mov        r1, r3
  0001fbf0:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fbf4:  sub        sp, fp, #8
  0001fbf8:  pop        {r4, fp, pc}
  0001fbfc:  andeq      sl, r2, r4, lsr #14
  0001fc00:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_SetColorFormat_LUT0 @ 0x0001fc04  size=132  ARM ===== */
  0001fc04:  push       {r4, fp, lr}
  0001fc08:  add        fp, sp, #8
  0001fc0c:  sub        sp, sp, #0x14
  0001fc10:  str        r0, [fp, #-0x18]
  0001fc14:  ldr        r4, [pc, #0x64]
  0001fc18:  add        r4, pc, r4
  0001fc1c:  ldr        r3, [pc, #0x60]
  0001fc20:  ldr        r3, [r4, r3]
  0001fc24:  ldr        r3, [r3]
  0001fc28:  add        r3, r3, #4
  0001fc2c:  mov        r0, r3
  0001fc30:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fc34:  mov        r3, r0
  0001fc38:  str        r3, [fp, #-0x10]
  0001fc3c:  ldr        r3, [fp, #-0x18]
  0001fc40:  uxtb       r3, r3
  0001fc44:  and        r3, r3, #1
  0001fc48:  uxtb       r2, r3
  0001fc4c:  ldr        r3, [fp, #-0x10]
  0001fc50:  bfi        r3, r2, #8, #1
  0001fc54:  str        r3, [fp, #-0x10]
  0001fc58:  ldr        r3, [pc, #0x24]
  0001fc5c:  ldr        r3, [r4, r3]
  0001fc60:  ldr        r3, [r3]
  0001fc64:  add        r2, r3, #4
  0001fc68:  ldr        r3, [fp, #-0x10]
  0001fc6c:  mov        r0, r2
  0001fc70:  mov        r1, r3
  0001fc74:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fc78:  sub        sp, fp, #8
  0001fc7c:  pop        {r4, fp, pc}
  0001fc80:  andeq      sl, r2, r0, lsr #13
  0001fc84:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_SetColorFormat_LUT1 @ 0x0001fc88  size=132  ARM ===== */
  0001fc88:  push       {r4, fp, lr}
  0001fc8c:  add        fp, sp, #8
  0001fc90:  sub        sp, sp, #0x14
  0001fc94:  str        r0, [fp, #-0x18]
  0001fc98:  ldr        r4, [pc, #0x64]
  0001fc9c:  add        r4, pc, r4
  0001fca0:  ldr        r3, [pc, #0x60]
  0001fca4:  ldr        r3, [r4, r3]
  0001fca8:  ldr        r3, [r3]
  0001fcac:  add        r3, r3, #4
  0001fcb0:  mov        r0, r3
  0001fcb4:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fcb8:  mov        r3, r0
  0001fcbc:  str        r3, [fp, #-0x10]
  0001fcc0:  ldr        r3, [fp, #-0x18]
  0001fcc4:  uxtb       r3, r3
  0001fcc8:  and        r3, r3, #1
  0001fccc:  uxtb       r2, r3
  0001fcd0:  ldr        r3, [fp, #-0x10]
  0001fcd4:  bfi        r3, r2, #0xc, #1
  0001fcd8:  str        r3, [fp, #-0x10]
  0001fcdc:  ldr        r3, [pc, #0x24]
  0001fce0:  ldr        r3, [r4, r3]
  0001fce4:  ldr        r3, [r3]
  0001fce8:  add        r2, r3, #4
  0001fcec:  ldr        r3, [fp, #-0x10]
  0001fcf0:  mov        r0, r2
  0001fcf4:  mov        r1, r3
  0001fcf8:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fcfc:  sub        sp, fp, #8
  0001fd00:  pop        {r4, fp, pc}
  0001fd04:  andeq      sl, r2, ip, lsl r6
  0001fd08:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_Acc_OnOff @ 0x0001fd0c  size=144  ARM ===== */
  0001fd0c:  push       {r4, fp, lr}
  0001fd10:  add        fp, sp, #8
  0001fd14:  sub        sp, sp, #0x14
  0001fd18:  str        r0, [fp, #-0x18]
  0001fd1c:  ldr        r4, [pc, #0x70]
  0001fd20:  add        r4, pc, r4
  0001fd24:  ldr        r3, [pc, #0x6c]
  0001fd28:  ldr        r3, [r4, r3]
  0001fd2c:  ldr        r3, [r3]
  0001fd30:  add        r3, r3, #8
  0001fd34:  mov        r0, r3
  0001fd38:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fd3c:  mov        r3, r0
  0001fd40:  str        r3, [fp, #-0x10]
  0001fd44:  ldr        r3, [fp, #-0x18]
  0001fd48:  cmp        r3, #1
  0001fd4c:  bne        #0x1fd60
  0001fd50:  ldr        r3, [fp, #-0x10]
  0001fd54:  orr        r3, r3, #1
  0001fd58:  str        r3, [fp, #-0x10]
  0001fd5c:  b          #0x1fd6c
  0001fd60:  ldr        r3, [fp, #-0x10]
  0001fd64:  bfc        r3, #0, #1
  0001fd68:  str        r3, [fp, #-0x10]
  0001fd6c:  ldr        r3, [pc, #0x24]
  0001fd70:  ldr        r3, [r4, r3]
  0001fd74:  ldr        r3, [r3]
  0001fd78:  add        r2, r3, #8
  0001fd7c:  ldr        r3, [fp, #-0x10]
  0001fd80:  mov        r0, r2
  0001fd84:  mov        r1, r3
  0001fd88:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fd8c:  sub        sp, fp, #8
  0001fd90:  pop        {r4, fp, pc}
  0001fd94:  muleq      r2, r8, r5
  0001fd98:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_rw_Start @ 0x0001fd9c  size=264  ARM ===== */
  0001fd9c:  push       {r4, fp, lr}
  0001fda0:  add        fp, sp, #8
  0001fda4:  sub        sp, sp, #0x14
  0001fda8:  str        r0, [fp, #-0x18]
  0001fdac:  ldr        r4, [pc, #0xe8]
  0001fdb0:  add        r4, pc, r4
  0001fdb4:  ldr        r3, [pc, #0xe4]
  0001fdb8:  ldr        r3, [r4, r3]
  0001fdbc:  ldr        r3, [r3]
  0001fdc0:  add        r3, r3, #8
  0001fdc4:  mov        r0, r3
  0001fdc8:  bl         #0x8588   // ->@plt _udd_ep_3dl_reg_GetReg
  0001fdcc:  mov        r3, r0
  0001fdd0:  str        r3, [fp, #-0x10]
  0001fdd4:  ldr        r3, [fp, #-0x18]
  0001fdd8:  cmp        r3, #1
  0001fddc:  bne        #0x1fe3c
  0001fde0:  ldr        r3, [fp, #-0x10]
  0001fde4:  orr        r3, r3, #0x100
  0001fde8:  str        r3, [fp, #-0x10]
  0001fdec:  ldr        r3, [pc, #0xac]
  0001fdf0:  ldr        r3, [r4, r3]
  0001fdf4:  ldr        r3, [r3]
  0001fdf8:  add        r2, r3, #8
  0001fdfc:  ldr        r3, [fp, #-0x10]
  0001fe00:  mov        r0, r2
  0001fe04:  mov        r1, r3
  0001fe08:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fe0c:  ldr        r3, [fp, #-0x10]
  0001fe10:  bfc        r3, #8, #1
  0001fe14:  str        r3, [fp, #-0x10]
  0001fe18:  ldr        r3, [pc, #0x80]
  0001fe1c:  ldr        r3, [r4, r3]
  0001fe20:  ldr        r3, [r3]
  0001fe24:  add        r2, r3, #8
  0001fe28:  ldr        r3, [fp, #-0x10]
  0001fe2c:  mov        r0, r2
  0001fe30:  mov        r1, r3
  0001fe34:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fe38:  b          #0x1fe94
  0001fe3c:  ldr        r3, [fp, #-0x10]
  0001fe40:  orr        r3, r3, #0x10
  0001fe44:  str        r3, [fp, #-0x10]
  0001fe48:  ldr        r3, [pc, #0x50]
  0001fe4c:  ldr        r3, [r4, r3]
  0001fe50:  ldr        r3, [r3]
  0001fe54:  add        r2, r3, #8
  0001fe58:  ldr        r3, [fp, #-0x10]
  0001fe5c:  mov        r0, r2
  0001fe60:  mov        r1, r3
  0001fe64:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fe68:  ldr        r3, [fp, #-0x10]
  0001fe6c:  bfc        r3, #4, #1
  0001fe70:  str        r3, [fp, #-0x10]
  0001fe74:  ldr        r3, [pc, #0x24]
  0001fe78:  ldr        r3, [r4, r3]
  0001fe7c:  ldr        r3, [r3]
  0001fe80:  add        r2, r3, #8
  0001fe84:  ldr        r3, [fp, #-0x10]
  0001fe88:  mov        r0, r2
  0001fe8c:  mov        r1, r3
  0001fe90:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fe94:  sub        sp, fp, #8
  0001fe98:  pop        {r4, fp, pc}
  0001fe9c:  andeq      sl, r2, r8, lsl #10
  0001fea0:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_reg_SetAddress @ 0x0001fea4  size=140  ARM ===== */
  0001fea4:  push       {fp, lr}
  0001fea8:  add        fp, sp, #4
  0001feac:  sub        sp, sp, #0x10
  0001feb0:  str        r0, [fp, #-8]
  0001feb4:  str        r1, [fp, #-0xc]
  0001feb8:  str        r2, [fp, #-0x10]
  0001febc:  ldr        r3, [pc, #0x64]
  0001fec0:  add        r3, pc, r3
  0001fec4:  ldr        r2, [fp, #-0x10]
  0001fec8:  cmp        r2, #1
  0001fecc:  bne        #0x1fef4
  0001fed0:  ldr        r2, [pc, #0x54]
  0001fed4:  ldr        r3, [r3, r2]
  0001fed8:  ldr        r3, [r3]
  0001fedc:  add        r2, r3, #0xc
  0001fee0:  ldr        r3, [fp, #-8]
  0001fee4:  mov        r0, r2
  0001fee8:  mov        r1, r3
  0001feec:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001fef0:  b          #0x1ff20
  0001fef4:  ldr        r2, [fp, #-0x10]
  0001fef8:  cmp        r2, #2
  0001fefc:  bne        #0x1ff20
  0001ff00:  ldr        r2, [pc, #0x24]
  0001ff04:  ldr        r3, [r3, r2]
  0001ff08:  ldr        r3, [r3]
  0001ff0c:  add        r2, r3, #0x10
  0001ff10:  ldr        r3, [fp, #-0xc]
  0001ff14:  mov        r0, r2
  0001ff18:  mov        r1, r3
  0001ff1c:  bl         #0x8744   // ->@plt _udd_ep_3dl_reg_SetReg
  0001ff20:  sub        sp, fp, #4
  0001ff24:  pop        {fp, pc}
  0001ff28:  strdeq     sl, fp, [r2], -r8
  0001ff2c:  andeq      r0, r0, r8, lsr #10

/* ===== _udd_ep_3dl_ctrl_ConfigBypassMode @ 0x0003ab38  size=40  ARM ===== */
  0003ab38:  push       {fp, lr}
  0003ab3c:  add        fp, sp, #4
  0003ab40:  sub        sp, sp, #8
  0003ab44:  str        r0, [fp, #-8]
  0003ab48:  mov        r0, #0
  0003ab4c:  bl         #0x8ba0   // ->@plt _udd_ep_3dl_reg_OnOff
  0003ab50:  mov        r3, #0
  0003ab54:  mov        r0, r3
  0003ab58:  sub        sp, fp, #4
  0003ab5c:  pop        {fp, pc}

/* ===== _udd_ep_3dl_ctrl_ConfigAccessMode @ 0x0003ab60  size=84  ARM ===== */
  0003ab60:  push       {fp, lr}
  0003ab64:  add        fp, sp, #4
  0003ab68:  sub        sp, sp, #8
  0003ab6c:  str        r0, [fp, #-8]
  0003ab70:  ldr        r3, [fp, #-8]
  0003ab74:  ldr        r3, [r3, #4]
  0003ab78:  cmp        r3, #1
  0003ab7c:  bne        #0x3ab8c
  0003ab80:  ldr        r0, [fp, #-8]
  0003ab84:  bl         #0x3a888
  0003ab88:  b          #0x3aba4
  0003ab8c:  ldr        r3, [fp, #-8]
  0003ab90:  ldr        r3, [r3, #4]
  0003ab94:  cmp        r3, #2
  0003ab98:  bne        #0x3aba4
  0003ab9c:  ldr        r0, [fp, #-8]
  0003aba0:  bl         #0x3a9e0
  0003aba4:  mov        r3, #0
  0003aba8:  mov        r0, r3
  0003abac:  sub        sp, fp, #4
  0003abb0:  pop        {fp, pc}

/* ===== _udd_ep_3dl_ctrl_ConfigProcessMode @ 0x0003abb4  size=116  ARM ===== */
  0003abb4:  push       {fp, lr}
  0003abb8:  add        fp, sp, #4
  0003abbc:  sub        sp, sp, #8
  0003abc0:  str        r0, [fp, #-8]
  0003abc4:  mov        r0, #1
  0003abc8:  bl         #0x8ba0   // ->@plt _udd_ep_3dl_reg_OnOff
  0003abcc:  mov        r0, #1
  0003abd0:  bl         #0x85ac   // ->@plt _udd_ep_3dl_reg_Acc_OnOff
  0003abd4:  mov        r0, #0
  0003abd8:  bl         #0x85ac   // ->@plt _udd_ep_3dl_reg_Acc_OnOff
  0003abdc:  ldr        r3, [fp, #-8]
  0003abe0:  ldr        r3, [r3, #0x14]
  0003abe4:  mov        r0, r3
  0003abe8:  bl         #0x8e1c   // ->@plt _udd_ep_3dl_reg_SelCbCr_ch
  0003abec:  ldr        r3, [fp, #-8]
  0003abf0:  ldr        r3, [r3, #0x10]
  0003abf4:  mov        r0, r3
  0003abf8:  bl         #0x8294   // ->@plt _udd_ep_3dl_reg_SelLUT
  0003abfc:  ldr        r3, [fp, #-8]
  0003ac00:  ldr        r2, [r3, #0x10]
  0003ac04:  ldr        r3, [fp, #-8]
  0003ac08:  ldr        r3, [r3, #0x18]
  0003ac0c:  mov        r0, r2
  0003ac10:  mov        r1, r3
  0003ac14:  bl         #0x3a820
  0003ac18:  mov        r3, #0
  0003ac1c:  mov        r0, r3
  0003ac20:  sub        sp, fp, #4
  0003ac24:  pop        {fp, pc}

