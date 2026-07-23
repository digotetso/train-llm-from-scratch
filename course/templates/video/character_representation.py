text = "Cat"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))

print()

text = "🐱"
print("Text:", text)
print("Code-point numbers:", [ord(character) for character in text])
print("UTF-8 byte numbers:", list(text.encode("utf-8")))
