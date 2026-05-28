# Temporary testing file for addressing modes
# Used for debugging and integration testing

from storage import memory, register
from addressing import AddressingMode

print("=== DIRECT ===")
memory.store(20, 999)
print(AddressingMode.direct(20))

print("\n=== INDIRECT ===")
memory.store(10, 20)
memory.store(20, 500)
print(AddressingMode.indirect(10))

print("\n=== REGISTER ===")
register.store(1, 123)
print(AddressingMode.register(1))

print("\n=== REGISTER INDIRECT ===")
register.store(1, 50)
memory.store(50, 777)
print(AddressingMode.register_indirect(1))

print("\n=== AUTOINC ===")
register.store(1, 30)
memory.store(30, 100)
print(AddressingMode.autoinc(1))
print(register.load(1))

print("\n=== AUTODEC ===")
register.store(1, 31)
memory.store(30, 200)
print(AddressingMode.autodec(1))
print(register.load(1))

print("\n=== INDEXED ===")
register.store(10, 5)  # XR register
memory.store(8, 888)

# XR already initialized in storage.py,
# but we'll overwrite for testing
register.store(10, 5)

print(AddressingMode.indexed(3))