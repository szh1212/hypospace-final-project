"""Frozen adapted baseline, selected using development data only."""
def transform(prompt, context):
    from hypospace_runner import upstream
    official,_=upstream()
    parser=object.__new__(official.Benchmark3D)
    unique={}
    for text in context['history']:
        structure=parser.parse_llm_response(text)
        if structure is not None:
            structure=structure.normalize()
            unique.setdefault(structure.get_hash(),structure.to_string())
    context=dict(context,history=list(unique.values()))
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
