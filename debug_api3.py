import asyncio, json, os
from playwright.async_api import async_playwright

OUT = "/Users/livrestrela/Documents/CCBU-Auto"

async def main():
    session_path = os.path.join(OUT, "ccbu_session.json")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=session_path,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        all_responses = {}
        
        async def on_response(response):
            url = response.url
            # Capture ALL XHR/fetch responses
            if not url.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico', '.woff', '.ttf', '.eot')):
                try:
                    body = await response.text()
                    if len(body) > 50 and len(body) < 200000:
                        body_lower = body.lower()
                        if any(kw in body_lower for kw in ['lessionid', 'courselist', '课程', 'workshopid', 'rows']):
                            if url not in all_responses:  # dedup
                                all_responses[url] = body[:3000]
                                print(f"\nCAPTURED: {url}", flush=True)
                                print(f"SAMPLE: {body[:500]}", flush=True)
                except:
                    pass

        page.on('response', on_response)

        ws_id = "d8e40285-8484-41ce-97ad-6f169850cc24"
        await page.goto(f"https://u.ccb.com/workshop/#/myworkshop/detail?id={ws_id}",
                        wait_until="load", timeout=30000)
        await asyncio.sleep(10)

        page.remove_listener('response', on_response)

        print(f"\n\n=== Captured {len(all_responses)} responses ===", flush=True)
        for url, body in all_responses.items():
            print(f"\nURL: {url}", flush=True)
            # Try to extract lessionIds
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    print(f"Keys: {list(data.keys())[:10]}", flush=True)
                    # Look for the course list
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > 0:
                            first = v[0] if isinstance(v[0], dict) else None
                            if first and 'lessionId' in first:
                                print(f"  FOUND courselist in key '{k}'! {len(v)} items", flush=True)
                                for item in v[:5]:
                                    print(f"    {item.get('lessionId','')[:20]} {item.get('editText','')} {item.get('title','')[:40]}", flush=True)
            except:
                pass

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
