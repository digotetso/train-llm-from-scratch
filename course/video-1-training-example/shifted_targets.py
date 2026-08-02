words = "The opposite of hot is cold".split()

inputs = words[:-1]
targets = words[1:]

print("inputs :", inputs)
print("targets:", targets)

print()

for input_word, target_word in zip(inputs, targets):
    print(input_word, "->", target_word)
