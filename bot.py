import asyncio
# import uvloop
#
# asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import datetime
import re
import shutil

import python_socks
from telethon import TelegramClient, events, Button

from aria2client import Aria2Client
from util import *

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

JSON_RPC_URL = os.getenv('JSON_RPC_URL')
JSON_RPC_TOKEN = os.getenv('JSON_RPC_TOKEN')

SEND_ID = int(os.getenv('SEND_ID'))
# Opsional
PROXY_IP = os.getenv('PROXY_IP', None)
PROXY_PORT = os.getenv('PROXY_PORT', None)

if PROXY_PORT is None or PROXY_IP is None:
    proxy = None
else:
    proxy = (python_socks.ProxyType.HTTP, PROXY_IP, int(PROXY_PORT))

bot = TelegramClient(None, API_ID, API_HASH, proxy=proxy).start(bot_token=BOT_TOKEN)

# Jalur absolut dari direktori khusus
out_dir = ''
# Apakah direktori default
is_def_dir = True

ar: Aria2Client = Aria2Client(JSON_RPC_URL, JSON_RPC_TOKEN, bot)


# Pintu masuk
async def main():
    await ar.init()

    ar.client.onDownloadStart(ar.on_download_start)
    ar.client.onDownloadPause(ar.on_download_pause)
    ar.client.onDownloadComplete(ar.on_download_complete)
    ar.client.onDownloadError(ar.on_download_error)
    bot.add_event_handler(BotCallbackHandler)
    print('Bot dimulai')


def get_menu(is_def_dir):
    return [
        [
            Button.text('⬇️ Mengunduh',resize=True),
            Button.text('⌛️ Menunggu',resize=True),
            Button.text('✅ Selesai/Berhenti',resize=True)
        ],
        [
            Button.text('⏸️ Menangguhkan tugas',resize=True),
            Button.text('▶️ Tugas pemulihan',resize=True),
            Button.text('❌ Menghapus tugas',resize=True),
        ],
        [
            Button.text('❌ ❌ Kosong selesai/berhenti',resize=True),
            Button.text('❎ Buka direktori khusus' if is_def_dir else '✅ Tutup direktori khusus',resize=True),
            Button.text('Tutup keyboard',resize=True),
        ],
    ]


# Panggilan balik tombol sebaris===============
@events.register(events.CallbackQuery)
async def BotCallbackHandler(event):
    # Panggilan balik setelah klik tombol
    # print(event.data)
    d = str(event.data, encoding="utf-8")
    [type, gid] = d.split('.', 1)
    if type == 'pause-task':
        await pause(event, gid)
    elif type == 'unpause-task':
        await unpause(event, gid)
    elif type == 'del-task':
        await delToTask(event, gid)


# Pemantauan pesan dimulai===============
@bot.on(events.NewMessage(pattern='/menu', from_users=SEND_ID))
async def send_welcome(event):
    await event.respond('Silakan pilih opsi', parse_mode='html', buttons=get_menu(is_def_dir))


@bot.on(events.NewMessage(pattern="/close"))
async def handler(event):
    await event.reply("Keyboard tertutup", buttons=Button.clear())


@bot.on(events.NewMessage(pattern="/path", from_users=SEND_ID))
async def path(event):
    text = event.text;
    text = text.replace('/path ', '')
    if not text.startswith('/'):
        await event.reply("Direktori harus berupa jalur absolut")
        return
    global out_dir
    out_dir = text
    await event.reply(f"Pengaturan direktori khusus: {out_dir}")


@bot.on(events.NewMessage(pattern="/getpath"))
async def getpath(event):
    if out_dir == '':
        await event.reply(f"Direktori khusus tidak disetel /help Lihat cara mengaturnya")
        return
    await event.reply(f"Direktori kustom: {out_dir}")


@bot.on(events.NewMessage(pattern="/start"))
async def handler(event):
    await event.reply("aria2 Untuk mengontrol robot, klik untuk menyalin send_id:<code>%s</code>" % (str(event.chat_id)), parse_mode='html')


@bot.on(events.NewMessage(pattern="/help"))
async def handler(event):
    await event.reply('''
Buka menu: <code>/menu</code>
Tutup menu: <code>/close</code>
Tetapkan direktori khusus (Anda perlu mengatur ulang setelah memulai ulang program): <code>/path jalur absolut</code>
Lihat direktori kustom pengaturan: <code>/getpath</code>
    ''', parse_mode='html')


@bot.on(events.NewMessage(from_users=SEND_ID))
async def send_welcome(event):
    text = event.raw_text
    print(str(datetime.datetime.now()) + ':' + text)
    if ar.client is None or ar.client.closed:
        # Mulai ulang klien
        await ar.init()
    # Pesan papan ketik
    if text == '⬇️ Mengunduh':
        await downloading(event)
        return
    elif text == '⌛️ Menunggu':
        await waiting(event)
        return
    elif text == '✅ Selesai/Berhenti':
        await stoped(event)
        return
    elif text == '⏸️ Menangguhkan tugas':
        await stopTask(event)
        return
    elif text == '▶️ Tugas pemulihan':
        await unstopTask(event)
        return
    elif text == '❌ Menghapus tugas':
        await removeTask(event)
        return
    elif text == '❌ ❌ Kosong selesai/berhenti':
        await removeAll(event)
        return
    elif 'Direktori kustom' in text:
        global is_def_dir
        if out_dir == '':
            await event.respond('Silakan atur direktori khusus terlebih dahulu, terlebih dahulu docker-compose.yml Konfigurasikan dan pasang direktori yang sesuai, misalnya: /path /down')
            return
        is_def_dir = not is_def_dir

        await event.respond(f'Status direktori khusus telah disetel ke {"off" if is_def_dir else "on"}', parse_mode='html',
                            buttons=get_menu(is_def_dir))
        return

    elif text == 'Tutup keyboard':
        await event.reply("Keyboard mati,/menu membuka keyboard", buttons=Button.clear())
        return

    exta_dic = dict()
    if not is_def_dir and out_dir != '':
        exta_dic['dir'] = out_dir

    # http Tautan magnet
    if 'http' in text or 'magnet' in text:

        # Pertandingan reguler
        res = re.findall('magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*', text)
        for text in res:
            await ar.client.addUri(
                uris=[text],
                options=exta_dic,
            )
        res2=text.split('\n')

        for text in res2:
            if text.endswith('.mp4') or '.mp4' in text:
                mp4Name = text.split('/')[-1]
                exta_dic['out'] = mp4Name
                await ar.client.addUri(
                    [text],
                    options=exta_dic,
                )
            else:
                await ar.client.addUri(
                    [text],
                    options=exta_dic,
                )

    try:
        if event.media and event.media.document:
            print(event.media.document.mime_type)
            if event.media.document.mime_type == 'application/x-bittorrent':
                print('Menerima benih')
                await event.reply('Menerima benih')
                path = await bot.download_media(event.message)
                print(path)

                gid = await ar.client.add_torrent(path, options=exta_dic, )
                print(gid)
                # os.unlink(path)
    except Exception as e:
        pass


# Pemantauan pesan berakhir===============


# Metode panggilan balik tombol teks=============================
async def downloading(event):
    tasks = await ar.client.tellActive()
    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang berjalan', parse_mode='html')
        return

    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        if fileName == '':
            continue
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + 'nama misi: <b>' + fileName + '</b>\njadwal: ' + prog + '\nukuran: ' + size + '\nkecepatan: ' + speed + '/s\n\n'
    if send_str == '':
        await event.respond('Beberapa tugas tidak dapat mengenali namanya, harap gunakan aria2Ng untuk melihatnya', parse_mode='html')
        return
    await event.respond(send_str, parse_mode='html')


async def waiting(event):
    tasks = await ar.client.tellWaiting(0, 30)
    # Filter tugas pengunduhan yang sesuai dengan send_id
    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang tertunda', parse_mode='markdown')
        return
    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + 'nama misi: ' + fileName + '\njadwal: ' + prog + '\nukuran: ' + size + '\nkecepatan: ' + speed + '\n\n'
    await event.respond(send_str, parse_mode='html')


async def stoped(event):
    tasks = await  ar.client.tellStopped(0, 500)

    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang selesai atau dihentikan', parse_mode='markdown')
        return
    send_str = ''
    for task in tasks:
        completedLength = task['completedLength']
        totalLength = task['totalLength']
        downloadSpeed = task['downloadSpeed']
        fileName = getFileName(task)
        prog = progress(int(totalLength), int(completedLength))
        size = byte2Readable(int(totalLength))
        speed = hum_convert(int(downloadSpeed))

        send_str = send_str + 'nama misi: ' + fileName + '\njadwal: ' + prog + '\nukuran: ' + size + '\nkecepatan: ' + speed + '\n\n'
    await event.respond(send_str, parse_mode='html')


async def stopTask(event):
    tasks = await ar.client.tellActive()

    # Filter tugas pengunduhan yang sesuai dengan send_id
    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang berjalan, tidak ada opsi jeda, harap tambahkan tugas terlebih dahulu', parse_mode='markdown')
        return
    # Gabungkan semua tugas
    buttons = []
    for task in tasks:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append([Button.inline(fileName, 'pause-task.' + gid)])

    await event.respond('Pilih tugas untuk dijeda ⏸️', parse_mode='html', buttons=buttons)


async def unstopTask(event):
    tasks = await ar.client.tellWaiting(0, 500)
    # Filter tugas yang sesuai dengan send_id
    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang dijeda, unduhan tidak dapat dilanjutkan', parse_mode='markdown')
        return
    buttons = []
    for task in tasks:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append([Button.inline(fileName, 'unpause-task.' + gid)])

    await event.respond('Silakan pilih tugas untuk dipulihkan ▶️', parse_mode='html', buttons=buttons)


async def removeTask(event):
    tempTask = []
    # Pengunduhan tugas
    tasks = await ar.client.tellActive()
    for task in tasks:
        tempTask.append(task)
    # Tugas yang tertunda
    tasks = await  ar.client.tellWaiting(0, 1000)
    for task in tasks:
        tempTask.append(task)
    if len(tempTask) == 0:
        await event.respond('Tidak ada tugas yang berjalan atau menunggu, tidak ada opsi hapus', parse_mode='markdown')
        return

    # Gabungkan semua tugas
    buttons = []
    for task in tempTask:
        fileName = getFileName(task)
        gid = task['gid']
        buttons.append([Button.inline(fileName, 'del-task.' + gid)])
    await event.respond('Silakan pilih tugas untuk dihapus ❌', parse_mode='html', buttons=buttons)


async def removeAll(event):
    # Pemfilteran selesai atau dihentikan
    tasks = await   ar.client.tellStopped(0, 500)

    if len(tasks) == 0:
        await event.respond('Tidak ada tugas yang harus diselesaikan', parse_mode='html')
        return

    for task in tasks:
        await  ar.client.removeDownloadResult(task['gid'])
        dir = task['dir']

    try:
        print('Direktori kosong ', dir)
        shutil.rmtree(dir, ignore_errors=True)
    except Exception as e:
        print(e)
        pass
    await event.respond('Tugas telah dihapus dan semua file telah dihapus', parse_mode='html')


# Metode callback tombol teks berakhir=============================


# Jeda panggilan
async def pause(event, gid):
    await  ar.client.pause(gid)


# Pemulihan panggilan
async def unpause(event, gid):
    await  ar.client.unpause(gid)


# Hapus panggilan
async def delToTask(event, gid):
    await  ar.client.remove(gid)
    await bot.send_message(SEND_ID, 'Tugas berhasil dihapus')


loop = asyncio.get_event_loop()
try:
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    pass
    
