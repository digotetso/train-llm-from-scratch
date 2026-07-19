## what is the best approach???

```
The current repo does not reset attention or add a special attention mask at document boundaries. Within a sampled window, tokens after EOS can still attend to earlier visible tokens from the previous document. This is a simple and common packing approach, though stricter document-separated attention is another possible design.
```