import discord
from discord.ext import commands
import youtube_dl
import asyncio

client = commands.Bot(command_prefix="?")

f = open("token.txt", "r")
token = f.readline()
# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ytdl_filesystem_options = {
    '--rm-cache-dir'
}

ffmpeg_options = {
    'options': '-vn'
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


@client.event
async def on_ready():
    print('Bot is online!')


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found.")


@client.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.channels, name='Teapot (Tpo)')
    await channel.send(f'Welcome {member.mention}!  Ready to jam out? See `?help` command for details!')


playlist = []  # Beginning of commands


@client.command(name='play', help='Plays music')
async def play(ctx):

    voice = ctx.message.guild.voice_client

    def is_connected():  # Tests if bot is connected to voice channel
        voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        return voice_client and voice_client.is_connected()

    url = ctx.message.content.lstrip('?play')
    playlist.append(url.lstrip(' '))

    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel")
        playlist.pop(0)
        return
    else:
        channel = ctx.message.author.voice.channel

    if is_connected():  # if connected to channel
        if voice.is_playing():  # url already added to the playlist, downloads each index
            index = len(playlist)-1
            player = await YTDLSource.from_url(playlist[index], loop=client.loop)
            await ctx.send('**Added:** {} to queue'.format(player.title))
            playlist[index] = player.title
        else:
            server = ctx.message.guild
            voice_channel = server.voice_client
            async with ctx.typing():
                try:
                    player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                    voice_channel.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(after_play(ctx), client.loop))
                    print(player.title)
                except Exception as x:
                    print(x)
            await ctx.send('**Now playing:** {}'.format(player.title))
            playlist[0] = player.title
            playlist.pop(0)

    else:  # if channel is not already connected
        await channel.connect()
        server = ctx.message.guild
        voice_channel = server.voice_client
        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                voice_channel.play(player,
                                   after=lambda e: asyncio.run_coroutine_threadsafe(after_play(ctx), client.loop))
                print(player.title)
            except Exception as x:
                print(x)
        await ctx.send('**Now playing:** {}'.format(player.title))
        playlist[0] = player.title


async def after_play(ctx):
    voice = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    playlist.pop(0)
    if len(playlist) > 0:
        server = ctx.message.guild
        voice_channel = server.voice_client
        player = await YTDLSource.from_url(playlist[0], loop=client.loop)
        voice_channel.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(after_play(ctx), client.loop))
        print(player.title)
    else:
        while True:  # Checks if voice is playing
            await asyncio.sleep(60)
            if not voice.is_playing():
                break
        await voice.disconnect()


@client.command(name='leave', help='Leaves the voice channel')
async def leave(ctx):
    def is_connected():
        discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not is_connected():
        await ctx.guild.voice_client.disconnect()
    else:
        await ctx.send("The bot is not connected to a voice channel.")


@client.command(name='pause', help='Pauses current song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


@client.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("The bot was not playing anything before this. Use play command")


@client.command(name='stop', help='Stops the song')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        playlist.clear()
    else:
        await ctx.send("The bot is not playing anything at the moment")


@client.command(name='queue', help='Lists music queue')
async def queue(ctx):
    index = 1
    voice_client = ctx.message.guild.voice_client
    if len(playlist) == 0:
        await ctx.send("There are no songs in the queue")
    if voice_client.is_playing():
        await ctx.send("Current: {}".format(playlist[0]))
    for i in playlist[1:]:
        await ctx.send("#{}: {}".format(index, i))
        index += 1


@client.command(name='q', help='Shorthand for queue - lists music queue')
async def q(ctx):
    index = 1
    voice_client = ctx.message.guild.voice_client
    if len(playlist) == 0:
        await ctx.send("There are no songs in the queue")
    if voice_client.is_playing():
        await ctx.send("Current: {}".format(playlist[0]))
    for i in playlist[1:]:
        await ctx.send("#{}: {}".format(index, i))
        index += 1


@client.command(name='skip', help='Skips the current song and plays the next one in queue')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        if len(playlist) == 1:
            await ctx.send("There are no more songs are playing")
        else:
            server = ctx.message.guild
            voice_channel = server.voice_client
            async with ctx.typing():
                try:
                    player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                    voice_channel.play(player,
                                       after=lambda e: asyncio.run_coroutine_threadsafe(after_play(ctx), client.loop))
                    print(player.title)
                except Exception as x:
                    print(x)
            await ctx.send('**Now playing:** {}'.format(player.title))
        playlist.pop(0)
    elif len(playlist) > 0:
        playlist.pop(0)
        await ctx.send("Removed from the queue")
    else:
        await ctx.send("The bot is not playing anything at the moment.")
    playlist[0] = player.title


@client.command(name='start', help='Plays the first song in queue')
async def start(ctx):
    voice_client = ctx.message.guild.voice_client
    if not voice_client.is_playing():
        server = ctx.message.guild
        voice_channel = server.voice_client
        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                voice_channel.play(player,
                                   after=lambda e: asyncio.run_coroutine_threadsafe(after_play(ctx), client.loop))
                print(player.title)
            except Exception as x:
                print(x)
        await ctx.send('**Now playing:** {}'.format(player.title))
    else:
        await ctx.send("It's already playing")


@client.command(name='clear', help='Clears music queue')
async def clear(ctx):
    del playlist[1:]
    await ctx.send("Queue cleared.")


@client.command(name='remove', help='Removes song at queue #')
async def remove(ctx):
    index = ctx.message.content.lstrip('?remove')
    index = int(index)
    playlist.pop(index)
    await ctx.send("You have removed the song at #{} from the queue".format(index))


@client.command(name='move', help='Moves song in queue to spot')
async def move(ctx):
    points = ctx.message.content.lstrip('?move ')
    list_points = list(points)
    tmp = playlist[int(list_points[0])]
    playlist[int(list_points[0])] = playlist[int(list_points[2])]
    playlist[int(list_points[2])] = tmp
    await ctx.send("You moved {} to number #{}!".format(playlist[int(list_points[2])], list_points[2]))


if __name__ == '__main__':
    client.run(token)
