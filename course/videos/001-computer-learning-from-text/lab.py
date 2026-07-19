text = "Cat"

print("Human text:", text)
print("Character numbers:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Can arithmetic use the raw string directly? No")
print("Learning begins after text is represented as numbers.")
