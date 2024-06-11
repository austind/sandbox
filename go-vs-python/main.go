package main

import (
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

func fetchURL(wg *sync.WaitGroup, url string, results chan<- string) {
	defer wg.Done()
	resp, err := http.Get(url)
	if err != nil {
		results <- fmt.Sprintf("Error fetching %s: %v", url, err)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		results <- fmt.Sprintf("Error reading response from %s: %v", url, err)
		return
	}
	results <- fmt.Sprintf("URL: %s - Status Code: %d - Body Length: %d", url, resp.StatusCode, len(body))
}

func main() {
	urls := []string{
		"https://example.com",
		"https://example.org",
		"https://example.net",
	}

	var wg sync.WaitGroup
	results := make(chan string, len(urls))

	startTime := time.Now()

	for _, url := range urls {
		wg.Add(1)
		go fetchURL(&wg, url, results)
	}

	wg.Wait()
	close(results)

	for result := range results {
		fmt.Println(result)
	}

	elapsedTime := time.Since(startTime)
	fmt.Printf("Execution time: %s\n", elapsedTime)
}
