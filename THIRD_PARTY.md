# Local inference assets

- [Transformers.js](https://github.com/huggingface/transformers.js), `@xenova/transformers` 2.17.2, Apache-2.0. The downloaded license is in `extension/vendor/TRANSFORMERS-LICENSE`.
- [ONNX Runtime](https://github.com/microsoft/onnxruntime), 1.14.0 browser WASM binaries distributed with Transformers.js, MIT.
- [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), Apache-2.0; quantized ONNX conversion from [Xenova/all-MiniLM-L6-v2](https://huggingface.co/Xenova/all-MiniLM-L6-v2), revision `751bff37182d3f1213fa05d7196b954e230abad9`.

Configuration follows the [Transformers.js local-model documentation](https://huggingface.co/docs/transformers.js/v2.17.2/custom_usage). Assets are fetched once during setup. Runtime model and WASM fetches stay on the extension origin; saved posts are not sent to these projects or hosts.
