
#test 1-----------------------------------
# from storage import memory, register
# from addressing import AddressingMode

# memory.store(20, 999)

# print(AddressingMode.direct(20))


#test2-----------------------------------
# from storage import memory
# from addressing import AddressingMode

# memory.store(10, 20)
# memory.store(20, 999)

# print(AddressingMode.indirect(10))


#test 3-----------------------------------
# from storage import register, memory
# from addressing import AddressingMode

# register.store(1, 50)
# memory.store(50, 777)

# print(AddressingMode.register_indirect(1))


#test 4-----------------------------------
from storage import register, memory
from addressing import AddressingMode

register.store(1, 30)

memory.store(30, 100)

print(AddressingMode.autoinc(1))

print(register.load(1))