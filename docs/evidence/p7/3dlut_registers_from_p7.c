/* ... 省略 ... */

// ==== FUN_004cf2e4 @ 0x4cf2e4 size=84 ====

undefined4 FUN_004cf2e4(undefined4 param_1,undefined4 param_2,undefined4 param_3)

{
  undefined1 uVar1;
  uint uVar2;
  undefined4 uVar3;
  
  uVar2 = FUN_000379c4(param_2);
  if (uVar2 == 0xffffffff) {
    return 0xffffffff;
  }
  uVar1 = FUN_004ceffc(uVar2 & 0xff);
  uVar3 = FUN_00037ec0(uVar2,param_1,param_3);
  FUN_004cf0fc(uVar1);
  return uVar3;
}



// ==== FUN_004cf3d4 @ 0x4cf3d4 size=40 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf3d4(int param_1)

{
  if (param_1 == 1) {
    _DAT_2082b000 = _DAT_2082b000 | 1;
  }
  else {
    _DAT_2082b000 = _DAT_2082b000 & 0xfffffffe;
  }
  return;
}



// ==== FUN_004cf3fc @ 0x4cf3fc size=24 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf3fc(uint param_1)

{
  _DAT_2082b004 = _DAT_2082b004 & 0xfffffffc | param_1 & 3;
  return;
}



// ==== FUN_004cf414 @ 0x4cf414 size=24 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf414(uint param_1)

{
  _DAT_2082b004 = _DAT_2082b004 & 0xffffffcf | (param_1 & 3) << 4;
  return;
}



// ==== FUN_004cf42c @ 0x4cf42c size=24 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf42c(uint param_1)

{
  _DAT_2082b004 = _DAT_2082b004 & 0xfffffeff | (param_1 & 1) << 8;
  return;
}



// ==== FUN_004cf444 @ 0x4cf444 size=24 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf444(uint param_1)

{
  _DAT_2082b004 = _DAT_2082b004 & 0xffffefff | (param_1 & 1) << 0xc;
  return;
}



// ==== FUN_004cf45c @ 0x4cf45c size=40 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf45c(int param_1)

{
  if (param_1 == 1) {
    _DAT_2082b008 = _DAT_2082b008 | 1;
  }
  else {
    _DAT_2082b008 = _DAT_2082b008 & 0xfffffffe;
  }
  return;
}



// ==== FUN_004cf484 @ 0x4cf484 size=48 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf484(int param_1)

{
  if (param_1 == 1) {
    _DAT_2082b008 = _DAT_2082b008 & 0xfffffeff;
  }
  else {
    _DAT_2082b008 = _DAT_2082b008 & 0xffffffef;
  }
  return;
}



// ==== FUN_004cf4b4 @ 0x4cf4b4 size=40 ====

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_004cf4b4(undefined4 param_1,undefined4 param_2,int param_3)

{
  if (param_3 != 1) {
    if (param_3 == 2) {
      _DAT_2082b010 = param_2;
    }
    return;
  }
  _DAT_2082b00c = param_1;
  return;
}



// ==== FUN_004cf4ec @ 0x4cf4ec size=32 ====
