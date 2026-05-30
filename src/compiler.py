# Filename: compiler.py
# This file contains the Instruction class for converting every instruction to binary Instruction
# Code. It also contains two global variables for converting operation into OpCode.

from bin_convert import HalfPrecision, Length
from storage import memory, register, variable

operations = [
    ["PRNT", "EOP"],                        
    ["MOV", "CALL", "RET", "SCAN"],                 
    ["JEQ", "JNE", "JLT", "JLE", "JGT", "JGE", "JMP"],  
    ["MOD", "ADD", "SUB", "MUL", "DIV"],            
]

operationCodes = [
    ["00", "01", "10", "11"],                           
    ["000", "001", "010", "011", "100", "101", "110"],  
]

class Instruction:

    # Coverts each dash to space, underscore to tab, dash+underscore to newline. Also converts the word minus to dash, and the word under to underscore.
    @staticmethod
    def decodeMSG(msg):
        return (
            msg.replace("-_", "\n")
            .replace("-", " ")
            .replace("_", "\t")
            .replace("minus", "-")
            .replace("under", "_")
        )

    # For easier understanding of which mode in encodeOp
    addressing_modes = {
        'register_mode':       '000',
        'register_indirect':   '001',
        'direct':              '010',
        'indirect':            '011',
        'indexed_regmem_disp': '100',
        'indexed_int_disp':    '101',
        'auto_increment':      '110',
        'auto_decrement':      '111',
    }   

    # Convert the operand into Operand Code.
    @staticmethod
    def encodeOp(operand):

        # Returns the Half Precision binary format of the operand.
        try:
            value = float(operand)
            return HalfPrecision.hpdec2bin(value)   
        except (ValueError, TypeError):
            pass

        # Stores the message to appropriate storage
        if operand.startswith('M:'):
            message = operand.replace('M:', '')
            decoded = Instruction.decodeMSG(message)
            index = variable.data['MI']
            variable.data['MSG'][index] = decoded
            variable.data['MI'] += 1
            return '0' * 10

        if '(' in operand and ')' in operand:
            inner_op = operand.replace('(', '').replace(')', '')

            # Creates the appropriate Addressing Mode binary code
            # relative (contains ‘Z’), based (contains ‘Y’), or indexed (contains ‘X’)
            if inner_op.startswith(('X', 'Y', 'Z')):
                inner_op = inner_op[1:]

                # Concatenates it with binary conversion 
                try:
                    disp_int = int(inner_op)
                    mode = Instruction.addressing_modes['indexed_int_disp']
                    sign_bit = '1' if disp_int < 0 else '0'
                    magnitude = Length.addZeros(abs(disp_int), 6)
                    addr_field = sign_bit + magnitude         

                # Concatenates it with the address (if register or memory) of the remaining string
                except ValueError:
                    addr = int(variable.load(inner_op))
                    mode = Instruction.addressing_modes['indexed_regmem_disp']
                    addr_bits = Length.addZeros(addr, 6)
                    type_bit = '0' if any(reg in inner_op for reg in ('R', 'PC', 'ACC', 'XR', 'BR', 'IR', 'CR', 'JR')) else '1'
                    addr_field = type_bit + addr_bits 
 
                return (mode + addr_field).zfill(10)
            
            elif inner_op.endswith('+'):
                reg_name = inner_op.replace('+', '')
                mode = Instruction.addressing_modes['auto_increment']
                addr = int(variable.load(reg_name))
                
            elif inner_op.endswith('-'):
                reg_name = inner_op.replace('-', '')
                mode = Instruction.addressing_modes['auto_decrement']
                addr = int(variable.load(reg_name))
                
            elif inner_op.startswith(('R', 'PC', 'ACC')):
                mode = Instruction.addressing_modes['register_indirect']
                addr = int(variable.load(inner_op))
                
            else:
                mode = Instruction.addressing_modes['indirect']
                addr = int(variable.load(inner_op))

            return (mode + Length.addZeros(addr, 7)).zfill(10)
        
        if operand.startswith(('R', 'PC', 'ACC', 'XR', 'BR', 'IR', 'CR', 'JR',
                                'B', 'F', 'P')):
            mode = Instruction.addressing_modes['register_mode']
        else:
            mode = Instruction.addressing_modes['direct']

        lookup_target = operand
        if operand.startswith(('Z', 'Y')):
            lookup_target = operand[1:] # Strips 'Z' or 'Y' to leave 'R2'

        # Get the address of the remaining string
  
        addr = int(variable.load(lookup_target))

        return (mode + Length.addZeros(addr, 7)).zfill(10)

    # Encode the instruction into Instruction Code.
    @staticmethod
    def encode(inst):

        parts = inst.split()
        op = parts[0]
        op_one = parts[1] if len(parts) > 1 else None
        op_two = parts[2] if len(parts) > 2 else None

        # Returns an instruction code of all zeros
        if op in ('EOP', 'FUNC'):
            return '0' * Length.instrxn 

        # Adds ‘BR’ to Block/Function Block
        if op == 'CB' or op == 'CF':
            op_two = op_one       
            op_one = 'BR'      
            op = 'ADD'

        # Subtracts operand from ‘JR’
        elif op == 'CMP':
            op_two = op_one      
            op_one = 'JR'
            op = 'SUB'

        # Moves relative address to operand
        elif op == 'ADDPC':
            op_two = 'Z' + op_two
            op = 'MOV'

        # Moves ‘PC’ to ‘CR’, then moves Function Block to ‘PC’
        elif op == 'CALL':
            inst_one = Instruction.encode('MOV PC CR')
            inst_two = Instruction.encode(f'MOV {op_one} PC')
            return [inst_one, inst_two]

        # Moves ‘CR’ to ‘PC’, then moves operand to ‘ACC’
        elif op == 'RET':
            inst_one = Instruction.encode('MOV CR PC')
            inst_two = Instruction.encode(f'MOV {op_one} ACC')
            return [inst_one, inst_two]

        # Creates the OpCode of the new Instruction.
        opcode = None
        for operation_cat, operation_ew in enumerate(operations):
            if op in operation_ew:
                ew_bits = operationCodes[0][operation_cat]
                cat_index = operation_ew.index(op)
                cat_bits = operationCodes[1][cat_index]
                opcode = ew_bits + cat_bits   
                break

        if opcode is None:
            raise ValueError(f"Unknown operation: {op}")
        if op in ('PRNT', 'SCAN') and op_one is not None:
            try:
                float(op_one)  # it's a number
                op_one = str(int(float(op_one)))  # keep as string address, not float
                # then force direct mode instead of immediate
            except ValueError:
                pass
        raw_op_one_code = Instruction.encodeOp(op_one)
        op_one_mode = raw_op_one_code[0:3]
        op_one_addr = raw_op_one_code[3:10]   

        ib = '0'
        rb = '0'
        op_two_mode = '0' * 3
        op_two_addr = '0' * 7
        extra_bits = '0' * 5  

        if op_two is not None:
            raw_op_two_code = Instruction.encodeOp(op_two)

            if len(raw_op_two_code) == Length.precision:
                ib          = '1'
                rb          = raw_op_two_code[0]      # sign bit goes into rb slot
                op_two_mode = raw_op_two_code[1:4]    # bits 1–3
                op_two_addr = raw_op_two_code[4:11]   # bits 4–10
                extra_bits  = raw_op_two_code[11:16]  # bits 11–15
            else:
                if op_two and op_two.startswith(('Z', 'Y')):
                    rb = '1'
                op_two_mode = raw_op_two_code[0:3]
                op_two_addr = raw_op_two_code[3:10]
        else:
            op_two_mode = '0' * 3
            op_two_addr = '0' * 7

        # Concatenate the Opcode to the encoded first operand. If there is a second operand, concatenate the encoded second operand to the Opcode and encoded first operand.
        instruction_code = (
            opcode +           # bits 0–4  (5 bits)
            ib +               # bit  5    (1 bit)
            op_one_mode +      # bits 6–8  (3 bits)
            op_one_addr +      # bits 9–15 (7 bits)
            rb +               # bit  16   (1 bit)
            op_two_mode +      # bits 17–19 (3 bits)
            op_two_addr +      # bits 20–26 (7 bits)
            extra_bits         # bits 27–31 (5 bits)
        )

        return instruction_code.zfill(Length.instrxn)

    # Encodes each instruction and put them to ‘PC’ in order except for ‘CF’ and ‘CB’.
    @staticmethod
    def encodeProgram(program):

        # Initialization
        address = int(variable.load('BR'))
        instructions = []
        block_counter = 0
        multiline_comment = False

        for line in program:

            line = line.strip()
            if not line:
                continue
            
            # Checks for multiline comments.
            if line.startswith('z'):
                multiline_comment = not multiline_comment
                continue

            # Skips if still in a multiline comment
            if multiline_comment:
                continue
            
            # Skips single-line comments
            if line.startswith('x'):
                continue

            parts = line.split()
            op = parts[0]

            # Store the current address in the block register operand
            if op in ('CB', 'CF'):
                block_name = parts[1]
                hp_addr = HalfPrecision.hpdec2bin(address + 1)
                register.store(int(variable.load(block_name)), hp_addr) 
                encoded = Instruction.encode(line)

                if isinstance(encoded, list):
                    for e in encoded:
                        instructions.insert(block_counter, e)
                        block_counter += 1
                        address += 1
                else:
                    instructions.insert(block_counter, encoded)
                    block_counter += 1
                    address += 1

            # Appends the encoded instruction at the last of the list
            else:
                encoded = Instruction.encode(line)
                if isinstance(encoded, list):
                    for e in encoded:
                        instructions.append(e)
                        address += 1
                else:
                    instructions.append(encoded)
                    address += 1
            
        br_addr = int(variable.load('BR'))
        register.store(br_addr, block_counter)

        for i, code in enumerate(instructions):
            memory.store(br_addr + i, code)


# ── HOW run.py CALLS THIS FILE ────────────────────────────
#
# run.py:
#   from compiler import Instruction
#
#   class Program:
#       def __init__(self, program):
#           Instruction.encodeProgram(program)  ← this is the only call
#
#   # After this, memory.data[9], memory.data[10], ... hold
#   # the 32-bit instruction strings that Program.run() will fetch.
#
# ── CODING ORDER (safest path) ────────────────────────────
#
#   1. Imports + operations + operationCodes  (get lookup tables right)
#   2. encodeOp() Branch 1 (immediate only)   → test
#   3. encodeOp() Branch 4 (register + direct) → test
#   4. encodeOp() Branch 3 (parentheses, one sub-branch at a time) → test each
#   5. encode() simple case: ADD R1 R2        → test
#   6. encode() aliased ops: CB, CF, CMP, CALL, RET, ADDPC
#   7. encodeProgram() — only after encode() is verified
#
# ── WHAT BREAKS IF SOMETHING IS WRONG ────────────────────
#
#   If encodeOp() returns wrong mode code → wrong addressing at runtime
#   If encode() wrong bit layout → run.py reads garbage opcodes
#   If encodeProgram() wrong addr sequence → instructions in wrong slots
#   All three failures are silent until run.py crashes or produces
#   wrong output — so test each method independently first.
# ============================================================