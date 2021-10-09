import discord
from discord.ext import commands
import youtube_dl
import asyncio
if __name__ == '__main__':

    client = commands.Bot(command_prefix="?")

    f = open("token.txt", "r")
    token = f.readline()

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
        'source_address': '0.0.0.0'
    }
    ffmpeg_options = {
        'options': '-vn'
    }
    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    class YTDLSource(discord.PCMVolumeTransformer):
        def __init__(self, source, *, data, volume=0.5):
            super().__init__(source, volume)
            self.data = data
            self.title = data.get('title')
            self.url = data.get('url')

        @classmethod
        async def from_url(cls, url, *, loop=None, stream=False):
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download="not stream"))

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

    @client.command(name='start', help='Plays the first song in queue')
    async def start(ctx):
        voice_client = ctx.message.guild.voice_client
        if not voice_client.is_playing():
            server = ctx.message.guild
            voice_channel = server.voice_client
            async with ctx.typing():
                player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                voice_channel.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                print(player.title)
            await ctx.send('**Now playing:** {}'.format(player.title))
        else:
            await ctx.send("It's already playing")

    @client.command(name='play', help='Plays music')
    async def play(ctx, url):
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

        if is_connected():
            if voice.is_playing():  # url already added to the playlist, downloads each index
                index = len(playlist)-1
                player = await YTDLSource.from_url(playlist[index], loop=client.loop)
                await ctx.send('**Added:** {} to queue'.format(player.title))
                playlist[index] = player.title
            else:
                server = ctx.message.guild
                voice_channel = server.voice_client
                async with ctx.typing():
                    player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                    voice_channel.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                    print(player.title)
                await ctx.send('**Now playing:** {}'.format(player.title))
                playlist[0] = player.title
                playlist.pop(0)
        else:
            await channel.connect()
            server = ctx.message.guild
            voice_channel = server.voice_client
            async with ctx.typing():
                player = await YTDLSource.from_url(playlist[0], loop=client.loop)
                voice_channel.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                print(player.title)
            await ctx.send('**Now playing:** {}'.format(player.title))
            playlist[0] = player.title

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
            await ctx.send("There is nothing in the queue")
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
                    player = await YTDLSource.from_url(playlist[1], loop=client.loop)
                    voice_channel.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                    print(player.title)
                await ctx.send('**Now playing:** {}'.format(player.title))
            playlist.pop(0)
        elif len(playlist) > 0:
            playlist.pop(0)
            await ctx.send("Removed from the queue")
        else:
            await ctx.send("The bot is not playing anything at the moment.")
        playlist[0] = player.title

    @client.command(name='clear', help='Clears music queue')
    async def clear(ctx):
        del playlist[1:]
        await ctx.send("Queue cleared.")

    @client.command(name='remove', help='Removes song at queue #')
    async def remove(ctx, index):
        index = ctx.message.content.lstrip('?remove')
        index = int(index)
        playlist.pop(index)
        await ctx.send("You have removed the song at #{} from the queue".format(index))

    client.run(token)