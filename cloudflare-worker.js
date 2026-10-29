export default {
    async fetch(request) {
      const url = new URL(request.url);
      const response = await fetch(
        `https://aelqazouiinsights.github.io/investment-management-with-python-and-machine-learning-specialization${url.pathname}${url.search}`,
        request
      );
  
      const result = new Response(response.body, response);
      result.headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
      result.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
      result.headers.set('Cross-Origin-Resource-Policy', 'same-origin');
      return result;
    }
  }
