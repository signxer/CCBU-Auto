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

        # 拦截所有API响应
        api_responses = []
        async def on_response(response):
            url = response.url
            if 'api.u.ccb.com' in url:
                try:
                    body = await response.json()
                    body_str = json.dumps(body, ensure_ascii=False)
                    if 'lessionId' in body_str or 'list' in body_str:
                        api_responses.append({'url': url, 'body': body})
                        print(f"\nAPI: {url[:120]}", flush=True)
                        print(f"  Body keys: {list(body.keys())[:10]}", flush=True)
                except:
                    pass
            elif 'api' in url and 'ccb' in url:
                print(f"Other API: {url}", flush=True)

        page.on('response', on_response)

        ws_id = "d8e40285-8484-41ce-97ad-6f169850cc24"
        await page.goto(f"https://u.ccb.com/workshop/#/myworkshop/detail?id={ws_id}",
                        wait_until="load", timeout=30000)
        await asyncio.sleep(15)

        page.remove_listener('response', on_response)

        print(f"\n\n=== Captured {len(api_responses)} API responses ===", flush=True)
        for resp in api_responses:
            print(f"\nURL: {resp['url'][:150]}", flush=True)
            body = json.dumps(resp['body'], ensure_ascii=False, indent=2)[:3000]
            print(f"Body: {body}", flush=True)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
