import elasticsearch_dsl as dsl

def ngram(min_gram=2, max_gram=4):
    base_name = "ngram_%d_%d" % (min_gram, max_gram)
    
    return dsl.analyzer(base_name + "_analyzer",
        tokenizer=dsl.tokenizer(base_name + "_tokenizer", 'nGram',
            min_gram=min_gram,
            max_gram=max_gram,
            token_chars=[ "letter", "digit" ]),
        filter=['lowercase'])
