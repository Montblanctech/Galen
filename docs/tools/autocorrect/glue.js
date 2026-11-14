/* T2b autocorrect: JS glue for t2b.wasm (plain C ABI, no wasm-bindgen).
   Strings go in as UTF-8 through t2b_alloc / t2b_free; results come back as JSON at t2b_out_ptr / t2b_out_len.
   Browser: T2B.load('t2b.wasm', 'model.bin', onProgress) -> Promise<scorer>; scorer.segment(text, k) -> object.
   Node:    require('./glue.js').create(wasmBytes, modelBytes). */
(function (root) {
  'use strict';
  var enc = new TextEncoder(), dec = new TextDecoder();

  function Scorer(instance) { this.ex = instance.exports; this.info = null; }
  Scorer.prototype._put = function (bytes) {
    var p = this.ex.t2b_alloc(bytes.length);
    new Uint8Array(this.ex.memory.buffer, p, bytes.length).set(bytes);   // view made after alloc (memory may grow)
    return p;
  };
  Scorer.prototype._out = function () {
    var p = this.ex.t2b_out_ptr(), n = this.ex.t2b_out_len();
    return dec.decode(new Uint8Array(this.ex.memory.buffer, p, n).slice());
  };
  /* raw JSON string for one line of text (any Greek: accents, lower case and spaces are normalised away) */
  Scorer.prototype.segmentJSON = function (text, k) {
    var b = enc.encode(String(text));
    var p = this._put(b);
    var r = this.ex.t2b_segment(p, b.length, k || 5);
    this.ex.t2b_free(p, b.length);
    var s = this._out();
    if (r < 0) throw new Error(s);
    return s;
  };
  Scorer.prototype.segment = function (text, k) { return JSON.parse(this.segmentJSON(text, k)); };

  function create(wasmBytes, modelBytes) {
    return WebAssembly.instantiate(wasmBytes, {}).then(function (res) {
      var t = new Scorer(res.instance);
      var m = modelBytes instanceof Uint8Array ? modelBytes : new Uint8Array(modelBytes);
      var p = t._put(m);
      var r = t.ex.t2b_init(p, m.length);
      t.ex.t2b_free(p, m.length);
      var info = t._out();
      if (r < 0) throw new Error('model: ' + info);
      t.info = JSON.parse(info);
      return t;
    });
  }

  /* fetch with byte progress (falls back to a plain read when the body is not streamable) */
  function fetchBytes(url, onProgress) {
    return fetch(url).then(function (resp) {
      if (!resp.ok) throw new Error(url + ': HTTP ' + resp.status);
      var total = +resp.headers.get('content-length') || 0;
      if (!resp.body || !resp.body.getReader || !onProgress) return resp.arrayBuffer().then(function (b) { return new Uint8Array(b); });
      var reader = resp.body.getReader(), parts = [], got = 0;
      function pump() {
        return reader.read().then(function (x) {
          if (x.done) {
            var out = new Uint8Array(got), o = 0;
            parts.forEach(function (c) { out.set(c, o); o += c.length; });
            return out;
          }
          parts.push(x.value); got += x.value.length; onProgress(got, total);
          return pump();
        });
      }
      return pump();
    });
  }

  function load(wasmUrl, modelUrl, onProgress) {
    return Promise.all([fetchBytes(wasmUrl), fetchBytes(modelUrl, onProgress)]).then(function (b) {
      return create(b[0], b[1]);
    });
  }

  var api = { create: create, load: load, fetchBytes: fetchBytes };
  if (typeof module === 'object' && module.exports) module.exports = api; else root.T2B = api;
})(typeof self !== 'undefined' ? self : this);
