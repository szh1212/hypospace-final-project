"""Dev ablations: coordinates, concise structure, and explicit reasoning."""
def structured(prompt, context):
    obs=context['observation']
    rows="\n".join(" ".join(obs[i:i+3]) for i in range(0,9,3))
    return f"""Reconstruct a 3x3 stack of cubes from this TOP VIEW:
{rows}
Rows run top to bottom; columns run left to right. Each displayed row is one grid row, not a height layer.
Layer 1 is the ground. Each higher layer must be a subset of the layer directly below it.
Every 0 in the top view MUST be 0 in ALL layers. Every 1 must be 1 in Layer 1 and may continue upward to height 2 or 3.
Use between 1 and 3 layers. Copy the top view exactly as Layer 1, then optionally add supported blocks above it.
Return ONLY the following format with exactly 3 rows of 3 space-separated binary digits per layer:
Structure:
Layer 1:
<row 1>
<row 2>
<row 3>
Layer 2:
<row 1>
<row 2>
<row 3>
Omit unused upper layers. Do not write explanations.
Prior outputs to avoid repeating:
{chr(10).join(context['history']) if context['history'] else '(none)'}
"""

def coordinates(prompt, context):
    occupied=[(i//3+1,i%3+1) for i,c in enumerate(context['observation']) if c=='1']
    return structured(prompt,context)+f"\nOccupied (row,column) positions, 1-based: {occupied}. ALL other positions must remain 0 in EVERY layer."

def reasoning(prompt, context):
    return coordinates(prompt,context)+"\nBefore Structure:, briefly identify occupied positions, choose heights 1..3 for them, and check support. Then output the final Structure: in the required Layer format."


def grounded(prompt, context):
    obs=context['observation']
    grid="\n".join(" ".join(obs[i:i+3]) for i in range(0,9,3))
    return f"""Output one stack of cubes as binary grid layers. Maximum height: 3.
The required bottom layer is given below. Copy it exactly, without moving, adding, or removing any 1.
Structure:
Layer 1:
{grid}
You may optionally append Layer 2 and Layer 3. Each appended layer must have 3 rows of 3 binary digits separated by spaces.
A 1 may appear only where the preceding layer has a 1. Thus each occupied column has height 1, 2, or 3.
Choose different column heights from prior attempts when possible. All other cells stay 0.
Return ONLY Structure: followed by Layer 1 and any chosen higher layers. No discussion or code fences.
Prior attempts (avoid repeating):
{chr(10).join(context['history']) if context['history'] else '(none)'}
END PRIOR ATTEMPTS.
The required Layer 1 for THIS answer is:
{grid}
"""
