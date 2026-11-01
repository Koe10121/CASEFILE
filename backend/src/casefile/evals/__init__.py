"""The eval harness: scripted interviews played against a real provider, then scored.

The engine already refuses anything a model gets wrong about the *truth*. What it can't
see is the *performance*: a suspect who breaks their own lie in dialogue, invents a
time, forgets to declare a fact it just said, or obeys a jailbreak. These evals measure
that, so models and prompts can be compared by numbers rather than by feel.
"""
