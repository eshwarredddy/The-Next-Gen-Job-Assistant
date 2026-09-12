from googlesearch import search

def test_google():
    query = 'site:linkedin.com/in "founder" "artificial intelligence" startup'
    results = search(query, num_results=5)
    
    output = []
    for r in results:
        output.append(r)
    print(output)

if __name__ == "__main__":
    test_google()
