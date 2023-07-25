import asyncio
import aiofiles
from aiohttp import ClientSession, ClientResponse, TCPConnector

import hashlib
import os
import re
from time import perf_counter
from random import uniform


class Requests(object):
    def __init__(self) -> None:
        self.url = ''
        self.headers = None,
        self.params = None,
        self.data = None,
        self.json = None,
        self.allow_redirects = True

    async def get(self, session: ClientSession) -> str:
        async with session.get(
            url=self.url,
            headers=self.headers,
            params=self.params,
            allow_redirects=self.allow_redirects
        ) as response:
            return await response.text()

    async def post(self, session: ClientSession) -> str:
        async with session.post(
                url=self.url,
                headers=self.headers,
                data=self.data,
                json=self.json,
                allow_redirects=self.allow_redirects
        ) as response:
            return await response.text()

    async def requests(
            self,
            url: str = '',
            method: str = 'GET',
            params: dict = None,
            data: dict = None,
            json: dict = None,
            headers: dict = None,
            allow_redirects: bool = True,
            semaphore: int = 5
    ) -> str:
        self.url = url
        self.headers = headers
        self.params = params
        self.data = data
        self.json = json
        self.allow_redirects = allow_redirects

        async with asyncio.Semaphore(semaphore):
            connect = TCPConnector(limit=1000)
            async with ClientSession(connector=connect) as session:
                if data or json or method == 'POST':
                    return await self.post(session=session)
                else:
                    return await self.get(session=session)


class Crawl(object):
    headers = {
        'Referer': 'https://www.woyaogexing.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }

    def __init__(
            self,
            start_url: str = ''
    ) -> None:
        self.start_url = start_url
        self.task = asyncio.Queue()

    @staticmethod
    def parse_image_url(response: str) -> any:
        """ 解析网页中出现的图片 url """
        image_url_template = '<a href="(.*?)" class="swipebox">'
        title_template = '<meta name="Description" content="(.*?)">'

        image_url_list = re.findall(image_url_template, response)
        title_list = re.findall(title_template, response)
        image_url_list = ['https:' + url for url in image_url_list if bool(url)]
        return image_url_list, title_list[0]

    async def _put_task(self, url: str) -> None:
        await self.task.put(url)

    async def on_found_atlas_url(self, url: str) -> None:
        """ 寻找所有的图集 url, 并且添加至 task queue 当中"""
        response = await Requests().requests(url=url, headers=self.headers)
        # 使用正则匹配出现的 atlas url
        atlas_url_template = '<a href="(.*?)" class="imgTitle" target="_blank" title=".*?">.*?</a>'

        atlas_url_list = re.findall(atlas_url_template, response)
        atlas_url_list = ['https://www.woyaogexing.com' + url for url in atlas_url_list if bool(url)]

        # 将找到的 url 传入任务队列当中
        for atlas_url in atlas_url_list:
            await self._put_task(atlas_url)

    async def download_image(self, url: str, title: str) -> None:
        # 定义一个下载器
        async with ClientSession() as session:
            async with session.get(url=url, headers=self.headers) as response:
                response_content = await response.content.read()

                # 检查目录是否存在
                if not os.path.exists('./atlas'):
                    os.mkdir('./atlas')

                file_name = re.sub('[\/:*"<>|? ]', '-', title)
                file_dir = os.path.join('./atlas', file_name)
                if not os.path.exists(file_dir):
                    os.mkdir(file_dir)

                # save...
                md5 = hashlib.md5()
                md5.update(url.encode('utf-8'))
                md5_key = md5.hexdigest()
                print(md5_key)
                image_file_path = os.path.join(file_dir, md5_key)
                async with aiofiles.open(f'{image_file_path}.jpg', mode='wb') as f:
                    await f.write(response_content)

    async def worker(self) -> None:
        url = await self.task.get()
        await self.crawl(url)
        self.task.task_done()

    async def crawl(self, url: str) -> None:
        await asyncio.sleep(uniform(2, 5))
        response = await Requests().requests(url=url, method='GET', headers=self.headers)

        # 提取页面中的 url
        image_url_list, title = self.parse_image_url(response)
        for url in image_url_list:
            await self.download_image(url, title)

    async def start(self) -> None:
        # 生成任务队列
        await self.on_found_atlas_url(self.start_url)
        while not self.task.empty():
            workers = [
                asyncio.create_task(self.worker())
                for _ in range(int(self.task.qsize()))
            ]

            await asyncio.gather(*workers)


async def main() -> None:
    spider = Crawl(start_url='https://www.woyaogexing.com/touxiang/index_2.html')
    await spider.start()


if __name__ == '__main__':
    start_time = perf_counter()
    asyncio.run(main())
    print('耗时 => ', perf_counter() - start_time)