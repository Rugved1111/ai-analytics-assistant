"""Step 3.2: what is an embedding? Turn sentences into vectors and compare them."""
from sentence_transformers import SentenceTransformer

# A small, free model that runs on your Mac (downloads about 90 MB the first time)
model = SentenceTransformer("all-MiniLM-L6-v2")

sentences = [
    "A VIP customer has lifetime sales of 10,000 or more.",
    "An order is late if it took more than 5 days to ship.",
    "Discount is stored as a fraction: 0.2 means 20% off.",
]
question = "Who are our most valuable clients?"

vectors = model.encode(sentences)
q_vector = model.encode(question)

print("Each text became", len(q_vector), "numbers.")
print("First 5 numbers of the question:", q_vector[:5].round(3))
print()
print("QUESTION:", question)
scores = model.similarity(q_vector, vectors)[0].tolist()
for score, sentence in sorted(zip(scores, sentences), reverse=True):
    print(f"{score:.2f}  {sentence}")
    