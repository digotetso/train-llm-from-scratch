sentence = "The opposite of hot is cold"
words = sentence.split()

print("Sentence:", sentence)
print("Words:", words)
print("Prediction positions:", len(words) - 1)
print()

print("Prefix questions:")
for position in range(1, len(words)):
    print(words[:position], "->", words[position])

print()
print("Shifted toy ID window:")
window = [7, 20, 4, 2, 6]
x = window[:-1]
y = window[1:]
print("window:", window)
print("x     :", x)
print("y     :", y)
