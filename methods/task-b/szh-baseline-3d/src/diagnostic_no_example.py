"""Dev-only ablation: remove the unrelated illustrative answer, keep task instructions."""
def transform(prompt, context):
    return prompt.split("Example of CORRECT output format", 1)[0]
