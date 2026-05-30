# =============================================================================
# test_isa.py — ISA Simulator Test Suite
# Tests every function across bin_convert, storage, addressing, compiler, run
# Run with: python test_isa.py
# =============================================================================

import sys

# ── Suppress the "No .isa file found" message from run.py on import ──────────
import io
_suppress = io.StringIO()
_real_stdout = sys.stdout
sys.stdout = _suppress

# Import all modules (storage side-effects run here)
from bin_convert import HalfPrecision, Length, BinaryFraction
from storage import memory, register, variable, Storage
from addressing import Access, AddressingMode
from compiler import Instruction
from run import Except, Program

sys.stdout = _real_stdout

# =============================================================================
# Test runner helpers
# =============================================================================

_results = []

def check(label, got, expected, *, tolerance=None):
    """
    Compare got vs expected. Use tolerance for floats.
    Prints PASS or FAIL and records the result.
    """
    if tolerance is not None:
        try:
            passed = abs(float(got) - float(expected)) <= tolerance
        except (TypeError, ValueError):
            passed = got == expected
    else:
        passed = (got == expected)

    status = "PASS" if passed else "FAIL"
    _results.append((status, label))

    if passed:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}")
        print(f"         expected : {repr(expected)}")
        print(f"         got      : {repr(got)}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def summary():
    total  = len(_results)
    passed = sum(1 for s, _ in _results if s == "PASS")
    failed = total - passed
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {passed}/{total} passed", end="")
    print(f"  |  {failed} failed" if failed else "  — all good!")
    print(f"{'='*60}\n")


# =============================================================================
# 1. bin_convert.py
# =============================================================================

section("1a — Length constants")
check("Length.whole == 5",          Length.whole,      5)
check("Length.precision == 16",     Length.precision,  16)
check("Length.fraction == 10",      Length.fraction,   10)
check("Length.instrxn == 32",       Length.instrxn,    32)
check("Length.dec_place == 2",      Length.dec_place,  2)
check("Length.opAddr == 7",         Length.opAddr,     7)
check("Length.opMode == 4",         Length.opMode,     4)
check("Length.operand == 11",       Length.operand,    11)

section("1b — Length.trimDec")
check("trimDec 3.14159 → 3.14",     Length.trimDec(3.14159),        3.14)
check("trimDec 0 → 0.0",            Length.trimDec(0),              0.0)
check("trimDec custom places=3",    Length.trimDec(1.23456, 3),     1.235)
check("trimDec string input",       Length.trimDec("2.71828"),      2.72)

section("1c — Length.addZeros")
check("addZeros int 5 to len 8",    Length.addZeros(5, 8),          "00000101")
check("addZeros str pad left",      Length.addZeros("101", 6),      "000101")
check("addZeros pad right",         Length.addZeros("101", 6, False), "101000")
check("addZeros already correct",   Length.addZeros("1010", 4),     "1010")

section("1d — BinaryFraction.idec2bin")
check("idec2bin 0.5 → 10 bits",     BinaryFraction.idec2bin(0.5),   "1000000000")
check("idec2bin 0.0",               BinaryFraction.idec2bin(0.0),   "0000000000")
check("idec2bin 0.25",              BinaryFraction.idec2bin(0.25),  "0100000000")

section("1e — HalfPrecision round-trip")
for n in [0, 1, 2, 3, 5, 8, 16, 32, 100, 1024]:
    hp  = HalfPrecision.hpdec2bin(n)
    back = HalfPrecision.hpbin2dec(hp)
    check(f"round-trip {n}",        back, float(n), tolerance=0.01)

check("hpdec2bin(0) length == 16",  len(HalfPrecision.hpdec2bin(0)),  16)
check("hpdec2bin(5) length == 16",  len(HalfPrecision.hpdec2bin(5)),  16)
check("hpdec2bin(5) starts with 0", HalfPrecision.hpdec2bin(5)[0],   "0")   # positive
check("hpdec2bin(-1) starts with 1",HalfPrecision.hpdec2bin(-1)[0],  "1")   # negative

section("1f — HalfPrecision.hpbin2bin and bin2hpbin")
bin5 = HalfPrecision.hpdec2bin(5)
check("bin2hpbin then hpbin2dec = 5",
      HalfPrecision.hpbin2dec(HalfPrecision.bin2hpbin("101")), 5.0, tolerance=0.01)


# =============================================================================
# 2. storage.py
# =============================================================================

section("2a — Storage.store and load — register")
register.store(1, 7)
check("register.store int, load back",  register.load(1),  7.0, tolerance=0.01)
register.store(2, 3.5)
check("register.store float",          register.load(2),  3.5, tolerance=0.01)

section("2b — Storage.store and load — memory")
memory.store(50, 42)
check("memory.store int, load back",    memory.load(50), 42.0, tolerance=0.01)
memory.store(51, 0)
check("memory.store 0",                 memory.load(51),  0.0, tolerance=0.01)

section("2c — Storage.store and load — HP binary address")
# Addresses passed as HP binary strings should be decoded first
hp_addr = HalfPrecision.hpdec2bin(50)
memory.store(50, 123)
check("load with HP binary address",    memory.load(hp_addr), 123.0, tolerance=0.01)

section("2d — variable storage (named registers)")
check("variable 'BR' → address 9",   variable.load('BR'),  9.0,  tolerance=0.01)
check("variable 'XR' → address 10",  variable.load('XR'),  10.0, tolerance=0.01)
check("variable 'PC' → address 13",  variable.load('PC'),  13.0, tolerance=0.01)
check("variable 'IR' → address 12",  variable.load('IR'),  12.0, tolerance=0.01)
check("variable 'JR' → address 14",  variable.load('JR'),  14.0, tolerance=0.01)
check("variable 'CR' → address 15",  variable.load('CR'),  15.0, tolerance=0.01)
check("variable 'R1' → address 1",   variable.load('R1'),  1.0,  tolerance=0.01)
check("variable 'R8' → address 8",   variable.load('R8'),  8.0,  tolerance=0.01)
check("variable 'B1' → address 57",  variable.load('B1'),  57.0, tolerance=0.01)
check("variable 'F1' → address 65",  variable.load('F1'),  65.0, tolerance=0.01)
check("variable 'A'  → address 1",   variable.load('A'),   1.0,  tolerance=0.01)

section("2e — Storage.dispStorage (smoke test, no crash)")
try:
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        register.dispStorage()
    check("dispStorage runs without error", True, True)
except Exception as ex:
    check("dispStorage runs without error", str(ex), "no error")

section("2f — Storage.setVariable")
import copy
_test_store = Storage()
Storage.setVariable(_test_store, "TEST_KEY", 99, 77)
check("setVariable: variable stores addr",  variable.load("TEST_KEY"), 99.0, tolerance=0.01)
check("setVariable: target stores value",   _test_store.load(99),      77.0, tolerance=0.01)


# =============================================================================
# 3. addressing.py
# =============================================================================

section("3a — Access.data")
# PC should follow var→reg path
pc_via_data = Access.data("PC", ["var", "reg"])
check("Access.data PC via var→reg is a number", isinstance(pc_via_data, (int, float)), True)

# Store known value in R1 and retrieve it via var→reg
register.store(1, 55)
r1_addr = variable.load("R1")   # 1.0
check("Access.data R1 via var→reg", Access.data("R1", ["var", "reg"]), 55.0, tolerance=0.01)

section("3b — Access.store")
Access.store("reg", 1, 77)
check("Access.store to reg[1]",  register.load(1), 77.0, tolerance=0.01)
Access.store("mem", 20, 88)
check("Access.store to mem[20]", memory.load(20),  88.0, tolerance=0.01)

section("3c — AddressingMode.immediate")
hp = HalfPrecision.hpdec2bin(9)
check("immediate(hp(9)) → 9.0",  AddressingMode.immediate(hp), 9.0, tolerance=0.01)
hp0 = HalfPrecision.hpdec2bin(0)
check("immediate(hp(0)) → 0.0",  AddressingMode.immediate(hp0), 0.0, tolerance=0.01)

section("3d — AddressingMode.register")
register.store(3, 13)
addr, val, typ = AddressingMode.register(3)
check("register mode — correct addr",    addr, 3)
check("register mode — correct val",     val,  13.0, tolerance=0.01)
check("register mode — storage is reg",  typ,  "reg")

section("3e — AddressingMode.direct")
memory.store(10, 77)
addr, val = AddressingMode.direct(10)
check("direct mode — correct addr",  addr, 10)
check("direct mode — correct val",   val,  77.0, tolerance=0.01)

section("3f — AddressingMode.register_indirect")
# reg[4] = 25, mem[25] = 66
register.store(4, 25)
memory.store(25, 66)
eff, val = AddressingMode.register_indirect(4)
check("reg_indirect — eff addr is 25",  eff, 25)
check("reg_indirect — value is 66",     val, 66.0, tolerance=0.01)

section("3g — AddressingMode.indirect")
# mem[30] = 40, mem[40] = 99
memory.store(30, 40)
memory.store(40, 99)
eff, val = AddressingMode.indirect(30)
check("indirect — eff addr is 40",  eff, 40)
check("indirect — value is 99",     val, 99.0, tolerance=0.01)

section("3h — AddressingMode.indexed")
# XR register address is 10 in register (value = xr = 77 from storage.py)
xr_addr = int(variable.load("XR"))   # register address of XR = 10
xr_val  = register.load(xr_addr)     # XR's actual value = 77
displace = 2
memory.store(int(xr_val + displace), 111)
eff, val = AddressingMode.indexed(displace)
check("indexed — eff addr = XR+displace", eff, int(xr_val + displace))
check("indexed — value at eff addr",      val, 111.0, tolerance=0.01)

section("3i — AddressingMode.autoinc")
# reg[5] = 60, mem[60] = 22 → returns (60, 22), reg[5] becomes 61
register.store(5, 60)
memory.store(60, 22)
eff, val = AddressingMode.autoinc(5)
check("autoinc — eff addr before inc",      eff,              60)
check("autoinc — value at addr",            val,              22.0, tolerance=0.01)
check("autoinc — register incremented",     register.load(5), 61.0, tolerance=0.01)

section("3j — AddressingMode.autodec")
# reg[6] = 62, mem[61] = 33 → decrements to 61 first, then reads mem[61]
register.store(6, 62)
memory.store(61, 33)
eff, val = AddressingMode.autodec(6)
check("autodec — eff addr after dec",       eff,              61)
check("autodec — value at addr",            val,              33.0, tolerance=0.01)
check("autodec — register decremented",     register.load(6), 61.0, tolerance=0.01)

section("3k — AddressingMode.relative")
# PC + displace → memory value
pc_addr = int(variable.load("PC"))
pc_val  = register.load(pc_addr)
displace = 1
eff_addr = int(pc_val + displace)
memory.store(eff_addr, 55)
val = AddressingMode.relative(displace)
check("relative — value at PC+displace",  val, 55.0, tolerance=0.01)

section("3l — AddressingMode.based")
# BR + displace → memory value
br_addr = int(variable.load("BR"))
br_val  = register.load(br_addr)
displace = 1
eff_addr = int(br_val + displace)
memory.store(eff_addr, 44)
val = AddressingMode.based(displace)
check("based — value at BR+displace",  val, 44.0, tolerance=0.01)


# =============================================================================
# 4. compiler.py
# =============================================================================

section("4a — Instruction.decodeMSG")
check("decodeMSG dash→space",       Instruction.decodeMSG("hello-world"),   "hello world")
check("decodeMSG under→tab",        Instruction.decodeMSG("hello_world"),   "hello\tworld")
check("decodeMSG dash-under→newline", Instruction.decodeMSG("a-_b"),        "a\nb")
check("decodeMSG word minus→dash",  Instruction.decodeMSG("minusone"),      "-one")
check("decodeMSG word under→underscore", Instruction.decodeMSG("underline"), "_line")
check("decodeMSG combined",         Instruction.decodeMSG("a-b_c"),         "a b\tc")

section("4b — Instruction.encodeOp — immediate")
r = Instruction.encodeOp("5.0")
check("encodeOp('5.0') length == 16",         len(r),    16)
check("encodeOp('5.0') == hpdec2bin(5)",      r,         HalfPrecision.hpdec2bin(5))
check("encodeOp('0') == hpdec2bin(0)",        Instruction.encodeOp("0"),
                                              HalfPrecision.hpdec2bin(0))
check("encodeOp('-1') starts with 1",         Instruction.encodeOp("-1.0")[0], "1")

section("4c — Instruction.encodeOp — register and direct modes")
r1 = Instruction.encodeOp("R1")
check("encodeOp('R1') length == 10",       len(r1),        10)
check("encodeOp('R1') mode bits == 0000",  r1[:4],         "0000")

a = Instruction.encodeOp("A")
check("encodeOp('A') length == 10",        len(a),         10)
check("encodeOp('A') mode bits == 0010",   a[:4],          "0010")

pc = Instruction.encodeOp("PC")
check("encodeOp('PC') is register mode",   pc[:4],         "0000")

acc = Instruction.encodeOp("ACC")
check("encodeOp('ACC') is register mode",  acc[:4],        "0000")

section("4d — Instruction.encodeOp — indirect modes")
ri = Instruction.encodeOp("(R1)")
check("encodeOp('(R1)') mode == 0001",      ri[:4],        "0001")
check("encodeOp('(R1)') length == 10",      len(ri),       10)

ind = Instruction.encodeOp("(A)")
check("encodeOp('(A)') mode == 0011",       ind[:4],       "0011")

section("4e — Instruction.encodeOp — auto-inc / auto-dec")
ai = Instruction.encodeOp("(R1+)")
check("encodeOp('(R1+)') mode == 0110",     ai[:4],        "0110")
check("encodeOp('(R1+)') length == 10",     len(ai),       10)

ad = Instruction.encodeOp("(R1-)")
check("encodeOp('(R1-)') mode == 0111",     ad[:4],        "0111")

section("4f — Instruction.encodeOp — indexed modes")
xi = Instruction.encodeOp("(X3)")
check("encodeOp('(X3)') int-indexed mode starts 0101",  xi[:4], "0101")

xr_enc = Instruction.encodeOp("(XR1)")
check("encodeOp('(XR1)') reg-indexed mode starts 0100", xr_enc[:4], "0100")

section("4g — Instruction.encode — basic operations")
def enc_ok(inst):
    r = Instruction.encode(inst)
    return isinstance(r, str) and len(r) == 32

check("encode('ADD R1 R2') length=32",   enc_ok("ADD R1 R2"),  True)
check("encode('SUB R1 R2') length=32",   enc_ok("SUB R1 R2"),  True)
check("encode('MUL R1 R2') length=32",   enc_ok("MUL R1 R2"),  True)
check("encode('DIV R1 R2') length=32",   enc_ok("DIV R1 R2"),  True)
check("encode('MOD R1 R2') length=32",   enc_ok("MOD R1 R2"),  True)
check("encode('MOV R1 R2') length=32",   enc_ok("MOV R1 R2"),  True)

# Execute bit and write bit positions
add_enc = Instruction.encode("ADD R1 R2")
check("ADD execute bit (pos 0) == 1",    add_enc[0],  "1")
check("ADD write bit (pos 1) == 1",      add_enc[1],  "1")

mov_enc = Instruction.encode("MOV R1 R2")
check("MOV execute bit (pos 0) == 0",    mov_enc[0],  "0")
check("MOV write bit (pos 1) == 1",      mov_enc[1],  "1")

section("4h — Instruction.encode — FUNC returns all zeros")
func_enc = Instruction.encode("FUNC")
check("encode('FUNC') == 32 zeros",      func_enc,  "0" * 32)

section("4i — Instruction.encode — aliased ops return correct types")
call_enc = Instruction.encode("CALL F1")
check("encode('CALL F1') returns list",           isinstance(call_enc, list),   True)
check("encode('CALL F1') list has 2 items",       len(call_enc),                2)
check("encode('CALL F1')[0] is 32 bits",          len(call_enc[0]),             32)
check("encode('CALL F1')[1] is 32 bits",          len(call_enc[1]),             32)

ret_enc = Instruction.encode("RET R1")
check("encode('RET R1') returns list",            isinstance(ret_enc, list),    True)
check("encode('RET R1') list has 2 items",        len(ret_enc),                 2)

cmp_enc = Instruction.encode("CMP R1")
check("encode('CMP R1') length=32",               len(cmp_enc),                 32)
check("encode('CMP R1') execute=1 write=1",       cmp_enc[:2],                  "11")

section("4j — Instruction.encodeProgram — stores instructions in memory")
# Use a fresh simple program and verify memory slots get filled
simple_prog = ["ADD R1 R2", "MOV R1 R2"]
Instruction.encodeProgram(simple_prog)
br_start = int(variable.load("BR"))
instr_0 = memory.data.get(br_start)
instr_1 = memory.data.get(br_start + 1)
check("encodeProgram: mem[BR] is 32-bit string",   isinstance(instr_0, str) and len(instr_0) == 32, True)
check("encodeProgram: mem[BR+1] is 32-bit string", isinstance(instr_1, str) and len(instr_1) == 32, True)

section("4k — Instruction.encodeProgram — comment skipping")
comment_prog = [
    "x this is a comment",
    "ADD R1 R2",
    "z",
    "MOV R1 R2",
    "z",
    "SUB R1 R2",
]
Instruction.encodeProgram(comment_prog)
br_start = int(variable.load("BR"))
i0 = memory.data.get(br_start)
i1 = memory.data.get(br_start + 1)
# Should have stored ADD and SUB; MOV was inside z...z block
add_code = Instruction.encode("ADD R1 R2")
sub_code = Instruction.encode("SUB R1 R2")
check("encodeProgram: x comment skipped, ADD at slot 0", i0, add_code)
check("encodeProgram: z block skipped, SUB at slot 1",   i1, sub_code)


# =============================================================================
# 5. run.py — Except class
# =============================================================================

section("5a — Except class")
e = Except("Test error")
check("Except occur default True",   e.isOccur(),    True)
check("Except message set",          e.message,      "Test error")

e2 = Except("No error", occur=False)
check("Except occur=False",          e2.isOccur(),   False)

e.setReturn(42)
check("Except setReturn / getReturn", e.getReturn(), 42)

import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    e.dispMSG()
check("Except dispMSG prints message", buf.getvalue().strip(), "Test error")

section("5b — Program.exception")
exc_inf = Program.exception("DivByZero", (0, 0))
check("DivByZero(0,0) → Infinity",    exc_inf.getReturn(),   "Infinity")
check("DivByZero(0,0) isOccur",       exc_inf.isOccur(),     True)

exc_und = Program.exception("DivByZero", (5, 0))
check("DivByZero(5,0) → undefined",   exc_und.getReturn(),   "undefined")


# =============================================================================
# 6. run.py — Program.execute
# =============================================================================

p = Program.__new__(Program)   # create instance without __init__ (no file needed)

section("6a — execute — arithmetic (write bit = 1)")
# ADD opcode: EW=11, Cat=001 → "11001"
check("execute ADD 3+4",        p.execute((3.0, 4.0),  "11001"),  7.0,  tolerance=0.01)
# SUB opcode: EW=11, Cat=010 → "11010"
check("execute SUB 10-3",       p.execute((10.0, 3.0), "11010"),  7.0,  tolerance=0.01)
# MUL opcode: EW=11, Cat=011 → "11011"
check("execute MUL 3*4",        p.execute((3.0, 4.0),  "11011"),  12.0, tolerance=0.01)
# DIV opcode: EW=11, Cat=100 → "11100"
check("execute DIV 10/2",       p.execute((10.0, 2.0), "11100"),  5.0,  tolerance=0.01)
# MOD opcode: EW=11, Cat=000 → "11000"
check("execute MOD 7%3",        p.execute((7.0, 3.0),  "11000"),  1.0,  tolerance=0.01)
# DIV by zero
import contextlib, io
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    dz = p.execute((5.0, 0.0), "11100")
check("execute DIV/0 → undefined",      dz,  "undefined")
with contextlib.redirect_stdout(buf):
    dz2 = p.execute((0.0, 0.0), "11100")
check("execute 0/0 → Infinity",         dz2, "Infinity")

section("6b — execute — jump operations (write bit = 0)")
jr_addr = int(variable.load("JR"))

# JEQ (JR == 0) → "10000"
register.store(jr_addr, 0)
check("execute JEQ JR=0 → True",        p.execute((0,0), "10000"), True)
register.store(jr_addr, 1)
check("execute JEQ JR≠0 → False",       p.execute((0,0), "10000"), False)

# JNE (JR != 0) → "10001"
register.store(jr_addr, 5)
check("execute JNE JR≠0 → True",        p.execute((0,0), "10001"), True)
register.store(jr_addr, 0)
check("execute JNE JR=0 → False",       p.execute((0,0), "10001"), False)

# JLT (JR < 0) → "10010"
register.store(jr_addr, -1)
check("execute JLT JR<0 → True",        p.execute((0,0), "10010"), True)
register.store(jr_addr, 0)
check("execute JLT JR=0 → False",       p.execute((0,0), "10010"), False)

# JLE (JR <= 0) → "10011"
register.store(jr_addr, 0)
check("execute JLE JR=0 → True",        p.execute((0,0), "10011"), True)
register.store(jr_addr, 1)
check("execute JLE JR>0 → False",       p.execute((0,0), "10011"), False)

# JGT (JR > 0) → "10100"
register.store(jr_addr, 3)
check("execute JGT JR>0 → True",        p.execute((0,0), "10100"), True)
register.store(jr_addr, 0)
check("execute JGT JR=0 → False",       p.execute((0,0), "10100"), False)

# JGE (JR >= 0) → "10101"
register.store(jr_addr, 0)
check("execute JGE JR=0 → True",        p.execute((0,0), "10101"), True)
register.store(jr_addr, -1)
check("execute JGE JR<0 → False",       p.execute((0,0), "10101"), False)

# JMP unconditional → "10110"
check("execute JMP always True",         p.execute((0,0), "10110"), True)


# =============================================================================
# 7. run.py — Program.write
# =============================================================================

section("7a — write — plain MOV (movecode=0)")
register.store(1, 0)
p.write((1, "reg"), 99.0, 0)
check("write MOV to reg[1]",  register.load(1), 99.0, tolerance=0.01)

memory.store(5, 0)
p.write((5, "mem"), 77.0, 0)
check("write MOV to mem[5]",  memory.load(5),  77.0, tolerance=0.01)

section("7b — write — CALL (movecode=1): copies PC to CR before move")
pc_addr = int(variable.load("PC"))
cr_addr = int(variable.load("CR"))
# Set known PC value
register.store(pc_addr, 20)
register.store(cr_addr, 0)
# Call write with movecode=1
p.write((1, "reg"), 55.0, 1)
check("write CALL: PC saved to CR",       register.load(cr_addr),  20.0, tolerance=0.01)
check("write CALL: src moved to dest",    register.load(1),         55.0, tolerance=0.01)

section("7c — write — RET (movecode=2): copies CR to PC before move")
cr_addr = int(variable.load("CR"))
pc_addr = int(variable.load("PC"))
register.store(cr_addr, 15)   # CR = 15 (return address)
register.store(pc_addr, 99)
register.store(1, 0)
p.write((1, "reg"), 88.0, 2)
check("write RET: CR restored to PC",     register.load(pc_addr),  15.0, tolerance=0.01)
check("write RET: src moved to dest",     register.load(1),         88.0, tolerance=0.01)


# =============================================================================
# 8. run.py — Program.getOp
# =============================================================================

section("8a — getOp — register mode (mode bits 000)")
register.store(1, 42)
# mode=000, addr=0000001 (address 1)
result = p.getOp("000" + "0000001")
check("getOp register: returns 3-tuple",       isinstance(result, tuple) and len(result)==3, True)
check("getOp register: addr == 1",             result[0],  1)
check("getOp register: val == 42",             result[1],  42.0, tolerance=0.01)
check("getOp register: type == 'reg'",         result[2],  "reg")

section("8b — getOp — direct mode (mode bits 010)")
memory.store(3, 77)
result = p.getOp("010" + "0000011")   # addr = 3
check("getOp direct: returns 2-tuple",         isinstance(result, tuple) and len(result)==2, True)
check("getOp direct: addr == 3",               result[0],  3)
check("getOp direct: val == 77",               result[1],  77.0, tolerance=0.01)

section("8c — getOp — register indirect mode (mode bits 001)")
register.store(4, 25)
memory.store(25, 66)
result = p.getOp("001" + "0000100")   # addr = 4
check("getOp reg_indirect: eff addr == 25",    result[0],  25)
check("getOp reg_indirect: val == 66",         result[1],  66.0, tolerance=0.01)

section("8d — getOp — indirect mode (mode bits 011)")
memory.store(30, 40)
memory.store(40, 99)
result = p.getOp("011" + "0011110")   # addr = 30
check("getOp indirect: eff addr == 40",        result[0],  40)
check("getOp indirect: val == 99",             result[1],  99.0, tolerance=0.01)

section("8e — getOp — auto-increment (mode bits 110)")
register.store(5, 60)
memory.store(60, 22)
result = p.getOp("110" + "0000101")   # addr = 5
check("getOp autoinc: eff addr == 60",         result[0],  60)
check("getOp autoinc: val == 22",              result[1],  22.0, tolerance=0.01)
check("getOp autoinc: reg[5] incremented",     register.load(5), 61.0, tolerance=0.01)

section("8f — getOp — auto-decrement (mode bits 111)")
register.store(6, 62)
memory.store(61, 33)
result = p.getOp("111" + "0000110")   # addr = 6
check("getOp autodec: eff addr == 61",         result[0],  61)
check("getOp autodec: val == 33",              result[1],  33.0, tolerance=0.01)
check("getOp autodec: reg[6] decremented",     register.load(6), 61.0, tolerance=0.01)


# =============================================================================
# 9. Integration — full encode → store → getOp round-trip
# =============================================================================

section("9 — Integration: encode → encodeProgram → getOp round-trip")
register.store(1, 7)    # R1 = 7
register.store(2, 3)    # R2 = 3

Instruction.encodeProgram(["ADD R1 R2"])
br_start = int(variable.load("BR"))
raw = memory.data.get(br_start)

check("integration: encoded instruction is 32-bit string",
      isinstance(raw, str) and len(raw) == 32, True)

# Decode the op1 field and confirm it points at R1 (addr 1)
op1code = raw[6:16]
result  = p.getOp(op1code)
check("integration: getOp on encoded R1 addr == 1",  result[0], 1)
check("integration: getOp on encoded R1 val == 7",   result[1], 7.0, tolerance=0.01)


# =============================================================================
# Final summary
# =============================================================================

summary()