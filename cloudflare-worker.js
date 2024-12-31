export default {
    async fetch(request) {
      const url = new URL(request.url);
      const response = await fetch(
        `https://aelqazouiinsights.github.io/investment-management-with-python-and-machine-learning-specialization${url.pathname}`,
        request
      );
  
      // Clone and modify response with required headers
      return new Response(response.body, {
        ...response,
        headers: {
          ...response.headers,
          'Cross-Origin-Embedder-Policy': 'require-corp',
          'Cross-Origin-Opener-Policy': 'same-origin',
          'Cross-Origin-Resource-Policy': 'cross-origin'
        }
      });
    }
  }