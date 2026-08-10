def build_context(results):

    context=""


    for r in results:

        context += f"""

Topic:
{r['metadata']['topic']}

Content:
{r['text']}

--------------------
"""

    return context