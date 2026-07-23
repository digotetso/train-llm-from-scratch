text = "Cat"

print("Human-readable text:", text)
print("Unicode code points:", [ord(character) for character in text])
print("UTF-8 bytes:", list(text.encode("utf-8")))
print("Ready for later AI training? Not yet")
print("Tokens, token IDs, and embeddings belong to later stages.")
