# Video 1 — Script 4: What Does It Mean for a Computer to Learn From Text?

## 00:00 The Result and the Question

You may already have seen an AI clarify an email, improve an essay sentence, or suggest a piece of code. The result can feel immediate: you write words, and useful new words appear. But that experience leaves a fair question unanswered. How can a system improve at tasks like these from written examples?

Language models can learn from many text examples. In practice, that collection is often very large, but large scale is not the definition of learning. The important idea is that examples give the system something to work from and something to improve against. We have experienced the useful output; that does not mean we have yet seen the machinery that produces it.

So let's begin this course with a map. It will show the whole journey from training text to repeated improvement. Then, instead of pretending that a quick tour makes every stop familiar, we will open one first step completely. By the end of this video, you will know why written text must take a numerical form before the later mathematical work can begin.

## 00:50 The Whole Journey in One Map

Here is the route. Read each arrow as a dependency: one stage supplies something the next stage needs. This is not a recipe you must memorize today. It is a promise about where our questions will lead.

```text
Training text
-> reusable text pieces [token]
-> one identifier per piece [token ID]
-> use the ID to select a learned number list [embedding]
-> model calculations
-> prediction
-> compare with the known training target
-> measured error
-> closed update method
-> changed parameters
-> repeat across examples
```

Start with training text: written examples provide the material for the journey. A later dividing rule turns that material into reusable text pieces; we call each resulting piece a token. Each defined piece receives one identifier, a token ID. That identifier lets the system select a learned number list, called an embedding. The learned list can then enter model calculations: the model is the mathematical prediction system whose internal numbers can change.

Those calculations produce a prediction, a numerical answer for the current training task. We compare that answer with the known training target already supplied by the example, which gives us a measured error: a number that says how far apart they are. A later update method uses that information to change the model's adjustable internal numbers, its parameters. Repeating that process across examples can make later answers less wrong.

Notice the discipline of this map. Each label gives us a job and a name, not the mechanism hiding inside it. `Cat` could enter as a label at the left of this route, but we will not make up a dividing rule, an identifier, a learned list, or a numerical answer for it. The arrows show dependency order, and any one arrow can hide a whole later lesson.

## 03:00 Close the Boxes We Have Not Opened

Being able to locate a labeled box is different from understanding how the box works. We can point to the dividing rule that produces tokens, but we have not learned that rule. We can point to token IDs and embeddings, but we have not learned how identifiers are assigned or how learned number lists are selected. We can point to model calculations, prediction math, target comparison, measured error, and the update method, but their mechanisms remain closed for now.

One distinction matters immediately because it keeps the route honest: token -> token ID -> use the ID to select an embedding. A token ID is an integer identifier. It tells the system which learned number list to select. A token ID does not become an embedding, and it is not represented by an embedding. These are different numerical objects with different jobs.

We will return to the dividing rule and token IDs in Video 11, to learned number lists in Video 23, and to prediction, comparison, measured error, and controlled updates in Videos 37-40. For now, those boxes stay closed. That restraint gives us one question we can truly open today: why must written text receive a numerical form before any later mathematical box can use it?
