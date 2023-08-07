import os
from pprint import pprint

import ujson
from aioaria2 import Aria2WebsocketClient

from util import getFileName, order_moov, imgCoverFromFile

SEND_ID = int(os.getenv('SEND_ID'))
UP_TELEGRAM = os.getenv('UP_TELEGRAM', 'False') == 'True'


class Aria2Client:
    rpc_url = ''
    rpc_token = ''
    bot = None
    client = None
    bot = None

    def __init__(self, rpc_url, rpc_token, bot):
        self.rpc_url = rpc_url
        self.rpc_token = rpc_token
        self.bot = bot

    async def init(self):
        self.client: Aria2WebsocketClient = await Aria2WebsocketClient.new(self.rpc_url, token=self.rpc_token,
                                                                           loads=ujson.loads,
                                                                           dumps=ujson.dumps, )

        # Batalkan panggilan balik terlebih dahulu
        # self.client.unregister(self.on_download_start, "aria2.onDownloadStart")
        # self.client.unregister(self.on_download_pause, "aria2.onDownloadPause")
        # self.client.unregister(self.on_download_complete, "aria2.onDownloadComplete")
        # self.client.unregister(self.on_download_error, "aria2.onDownloadError")


    async def on_download_start(self, trigger, data):
        print(f"===========unduh mulai {data}")
        gid = data['params'][0]['gid']
        # Kueri apakah itu file dengan nilai fitur terikat
        tellStatus = await self.client.tellStatus(gid)
        await self.bot.send_message(SEND_ID,
                                    f'{getFileName(tellStatus)} Tugas telah mulai diunduh... \n jalur yang sesuai: {tellStatus["dir"]}',
                                    parse_mode='html')

    async def on_download_pause(self, trigger, data):
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        filename = getFileName(tellStatus)
        print('panggilan balik ===> tugas: ', filename, 'berhenti sebentar')
        # await bot.send_message(SEND_ID, filename + ' Tugas telah berhasil dijeda')

    async def on_download_complete(self, trigger, data):
        print(f"===========Pengunduhan selesai {data}")
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        files = tellStatus['files']
        # unggah berkas
        for file in files:
            path = file['path']
            await self.bot.send_message(SEND_ID,
                                        'Pengunduhan selesai===> ' + path,
                                        )
            # Kirim pesan bahwa file berhasil diunduh

            if UP_TELEGRAM:
                if '[METADATA]' in path:
                    os.unlink(path)
                    return
                print('mulai mengunggah, file jalur:' + path)
                msg = await self.bot.send_message(SEND_ID,
                                                  'mengunggah===> ' + path,
                                                  )

                async def callback(current, total):
                    # print("\r", 'mengirim', current, 'out of', total,
                    #       'bytes: {:.2%}'.format(current / total), end="", flush=True)
                    # await bot.edit_message(msg, path + ' \nmengunggah : {:.2%}'.format(current / total))
                    print(current / total)

                try:
                    # Tangani unggahan mp4 secara terpisah
                    if '.mp4' in path:

                        pat, filename = os.path.split(path)
                        await order_moov(path, pat + '/' + 'mo-' + filename)
                        # tangkapan layar
                        await imgCoverFromFile(path, pat + '/' + filename + '.jpg')
                        os.unlink(path)
                        await self.bot.send_file(SEND_ID,
                                                 pat + '/' + 'mo-' + filename,
                                                 thumb=pat + '/' + filename + '.jpg',
                                                 supports_streaming=True,
                                                 progress_callback=callback
                                                 )
                        await msg.delete()
                        os.unlink(pat + '/' + filename + '.jpg')
                        os.unlink(pat + '/' + 'mo-' + filename)
                    else:
                        await self.bot.send_file(SEND_ID,
                                                 path,
                                                 progress_callback=callback
                                                 )
                        await msg.delete()
                        os.unlink(path)

                except FileNotFoundError as e:
                    print('berkas tidak ditemukan')

    async def on_download_error(self, trigger, data):
        print(f"===========kesalahan unduhan {data}")
        gid = data['params'][0]['gid']

        tellStatus = await self.client.tellStatus(gid)
        errorCode = tellStatus['errorCode']
        errorMessage = tellStatus['errorMessage']
        print('Tugas', gid, 'kode kesalahan', errorCode, 'pesan eror：', errorMessage)
        if errorCode == '12':
            await self.bot.send_message(SEND_ID, ' Tugas sedang mengunduh, harap hapus dan coba lagi')
        else:
            await self.bot.send_message(SEND_ID, errorMessage)

        pprint(tellStatus)
        
