"""Adapted prompts. Inputs contain observations and parsed history only."""
def causal(meta, observations, history):
    return f'''Infer one directed acyclic causal graph on nodes {", ".join(meta["nodes"])}.
Use at most {meta["max_edges"]} edges. No self loops, cycles, or other nodes.
When a node is perturbed its own value is 0. Every other node is 1 exactly when it is reachable by a directed path from the perturbed node; otherwise it is 0. Match ALL observations, including every zero.
Observations:
{observations}
Return exactly one line, no explanation:
Graph: <source>-><target>, <source>-><target>, ...
For an empty graph use Graph: No edges
Prior parsed unique outputs to avoid repeating:
{chr(10).join(history) if history else "(none)"}
'''

def genetic(meta, observations, history):
    descriptions={'AND':'AND: result is 1 only when both inputs are 1.','OR':'OR: result is 1 when at least one input is 1.','NOT':'NOT: invert the input bit.','NOR':'NOR: result is 1 only when both inputs are 0.'}
    rules='\n'.join(descriptions[o] for o in sorted(meta['operators']))
    return f'''Infer one Boolean expression matching ALL observed input-output pairs.
Allowed variables: {", ".join(meta["variables"])}.
Allowed operators: {", ".join(sorted(meta["operators"]))}. Use ONLY this list.
{rules}
Every row lists fixed variable values followed by the required expression output. Substitute those values into your expression: it must give the displayed output on EVERY row.
Use no constants, other variables or other operators. Maximum expression depth is {meta["max_depth"]}: a variable has depth zero and an operator adds one to its deepest child.
Structural identity uses commutativity, AND/OR idempotence and associativity flattening. Do not equate expressions using distributivity, absorption or De Morgan rules.
Observations:
{observations}
Return one line only, with uppercase operators, lowercase variables and parentheses for grouping:
Expression: <expression>
Prior parsed unique outputs to avoid repeating:
{chr(10).join(history) if history else "(none)"}
'''
