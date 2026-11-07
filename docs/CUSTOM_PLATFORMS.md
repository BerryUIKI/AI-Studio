# Custom platforms and calling code

Open **Cloud Providers → Add platform**. Choose a unique `custom-` ID, request endpoint, exact model IDs and the image actions supported by your integration. Save API keys in the separate protected key field. Keys are not part of canvas projects, REST templates or calling-code exports. Changing a platform does not silently switch providers or models.

## Calling methods

- **REST configuration:** JSON placeholders such as `{{model}}`, `{{prompt}}`, `{{width}}`, `{{height}}`, `{{input_image}}` and `{{mask_image}}` substitute action inputs. A whole placeholder preserves its JSON type. A result path such as `data.0.url` selects either an HTTPS image URL or base64 bytes. Templates do not evaluate code.
- **JavaScript adapter:** implement `async function execute(input, ctx)`. The embedded runtime exposes the broker below, without Node.js, filesystem or `fetch` globals.
- **Python adapter:** implement `async def execute(input, ctx)` or a synchronous `execute`. Python is trusted code with OS and network access. An owned worker is not a security sandbox.
- **Python with isolated SDK:** additionally provide pinned requirements with SHA256 hashes for every transitive dependency, approve the exact revision, then select **Prepare isolated SDK environment**. Packages install under application data, separately from Berry's core Python and local engines. Preparation downloads packages without calling the model provider. Only binary distributions are accepted.

An SDK requirements line has this form (replace the version and hash with the actual reviewed wheel metadata):

```text
package-name==1.2.3 --hash=sha256:<64 lowercase hexadecimal characters>
```

Calling code requires approval for its current descriptor, source and dependency manifest. Editing any configuration resets new approval; the saved revision remains executable only if its exact hash is approved. SDK raw-key access is separately disabled by default. When explicitly enabled, that SDK revision receives only its own platform key as `ctx.api_key`; fixture tests withhold it. Direct SDK calls can bypass broker accounting and may incur charges. Berry does not enforce a hard spending limit for trusted Python code.

## Shared adapter protocol

`input` contains the selected `model`, `action`, `prompt`, dimensions and action parameters. Selected source/mask images are PNG data URLs in `input_image`/`mask_image`; masks use white for edit and black for protection. `variation_nonce` distinguishes an explicitly requested new variation. It is not evidence of provider seed support.

Both languages support these asynchronous methods:

- `ctx.request({method, path, body, params})`: send JSON to the configured origin. `method` is `GET` or `POST`; `path` is optional and cannot change origin. The host supplies the configured bearer/header credential. Code cannot override headers or follow redirects. Requests are not automatically retried.
- `ctx.wait(milliseconds)`: wait between polling attempts, from 0 through 5000 milliseconds per call, within the total worker deadline.
- `ctx.job_id(id)`: record a provider job identifier before polling it. Await this call so the task history retains the identifier if execution is interrupted. IDs must contain 1–256 characters without control characters or credentials.

For example, a JavaScript polling integration can persist the submitted job before requesting its result:

```javascript
async function execute(input, ctx) {
  const job = await ctx.request({path: 'submit', body: {model: input.model, prompt: input.prompt}});
  await ctx.job_id(job.id);
  const result = await ctx.request({method: 'GET', path: 'result', params: {id: job.id}});
  return {type: 'image', value: {url: result.image_url}};
}
```

This illustrates the protocol, not any provider's endpoint contract. Implement that provider's bounded polling/status handling before live use. Python uses the same dictionary fields, for example `await ctx.job_id(job['id'])`.

Outputs follow the five execution types: `string`, `image`, `audio`, `video`, `json`. The image canvas specifically requires `{type: 'image', value: {url: 'https://…'}}` or `{type: 'image', value: {b64_json: '…'}}`. Berry downloads without provider authorization headers, decodes the actual bytes and saves a managed resource. Invalid media is not adopted. Optional `reported_model` is retained as adapter-reported information, without claiming a verified remote weight revision. Raw request/image payloads are not copied into generation provenance.

Workers have bounded IPC, deadlines and broker request counts. Defaults are 120 seconds per HTTP request, 150 seconds per code execution and 4 broker requests; configurable maxima are 180 seconds and 16 requests. IPC/JSON responses are bounded to 16 MiB. JavaScript additionally has CPU/memory limits. Windows owned job objects bound worker memory/process count; POSIX workers use dedicated process groups. These ownership measures do not turn trusted Python into an OS sandbox.

## Fixtures, cancellation and cache

Save a revision, then use **Run broker fixture** with synthetic inputs and a mock JSON response. This replaces broker HTTP and withholds SDK keys. It does not prevent Python from making its own OS/network calls. Run only reviewed code. Fixture success verifies mapping/protocol behavior, not live provider access, model quality, price, SDK compatibility or packaged-runtime readiness.

Queued canvas tasks pin the descriptor, credential and dependency revisions. Cache identity also includes adapter code, endpoint/runtime/model identity, inputs and source/mask contents. A changed or unapproved revision fails closed; a missing output is regenerated only by an explicit execution request. A cache repeat makes no provider request. New variations change the nonce. SDK package-byte changes invalidate its dependency identity.

Cancelling a custom task stops the local broker operation and Berry-owned worker tree. It never terminates an unrelated external engine. Work already submitted to a provider can continue and incur charges; those tasks retain an unknown remote outcome instead of claiming remote cancellation. Consult the stored provider job ID and the provider console before explicitly retrying. Shutdown also closes owned workers. No automatic paid retry or provider fallback occurs.

Removing a platform deletes its descriptor and stored key after local confirmation. Existing images and task history remain; isolated SDK files are retained under application data. Live provider and clean packaged-runtime acceptance remain separate release evidence.
