# Third-party notices

The Python runtime has no third-party dependencies.

Browser acceptance uses [Playwright](https://playwright.dev/) 1.59.1 and `playwright-core` 1.59.1 as development dependencies under Apache-2.0. The lock also contains the optional macOS dependency `fsevents` 2.3.2 under MIT. They are downloaded from npm and are not vendored in this repository. Chromium downloaded by Playwright retains its own upstream licenses.

This notice describes source-repository development dependencies only. A future binary, container, hosted service, font, image, model, or dataset distribution must produce its own complete bill of materials and license review.
