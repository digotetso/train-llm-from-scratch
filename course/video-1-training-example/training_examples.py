sentence = "The opposite of hot is cold"
words = sentence.split()

print("Sentence:", sentence)
print("Words:", words)
print("Number of words:", len(words))

print()

for position in range(1, len(words)):
    print(words[:position], "->", words[position])
