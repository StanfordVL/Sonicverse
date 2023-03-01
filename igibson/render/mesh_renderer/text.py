import os
from collections import deque

import freetype as ft
import matplotlib.pyplot as plt
import numpy as np

from igibson import assets_path


class Character(object):
    """
    Manages data for a single character.
    """

    def __init__(self, tex_id, size, bearing, advance, buffer):
        """
        :param tex_id: OpenGL texture id for this character
        :param size: list containing [x, y] size of character
        :param bearing: list containing [left, top] bearing of character
        :param advance: int representing offset to advance to get to next glyph
        :param buffer: raw character pixel values
        """
        self.tex_id = tex_id
        self.size = size
        self.bearing = bearing
        self.advance = advance
        self.buffer = buffer

    def viz_char(self):
        """
        Debug method for visualizing a character.
        """
        img_data = np.array(self.buffer)
        img_data = img_data.reshape((self.size[1], self.size[0]))
        plt.imshow(img_data, cmap="gray", vmin=0, vmax=255)
        plt.show()


class TextManager(object):
    """
    Manages character information and other centralized text info.
    """

    def __init__(self, renderer):
        """
        :param renderer: the renderer that will render the fonts
        """
        self.renderer = renderer
        if not self.renderer:
            raise ValueError("A renderer is required to render text")
        self.supported_fonts = ["OpenSans", "SourceSansPro"]
        self.supported_styles = ["Bold", "Italic", "Regular"]
        self.font_folder = os.path.join(assets_path, "fonts")
        # Font data is stored in dictionary - TODO: Keep this here? Change data type based on what is stored?
        self.font_data = {}
        # List of all texture ids - used when cleaning up text manager
        self.tex_ids = []

    def gen_text_fbo(self):
        """
        Generates the separate framebuffer used to render all text.
        """
        self.FBO, self.render_tex = self.renderer.r.genTextFramebuffer()

    def get_render_tex(self):
        """
        Returns the render texture belonging to the TextManager,
        which contains all Text that has the render_to_tex flag set to True.
        """
        return self.render_tex

    def load_font(self, font_name, font_style, font_size):
        """
        Loads font. TextManager stores data for each font, and only loads once for efficiency.
        Thus multiple Text objects can access the same font without loading it multiple times.
        :param font_name: name of font
        :param font_style: style of font (must be regular, italic or bold)
        :param font_size: vertical height of font letters in pixels
        """
        # Test if this font, style combination has already been loaded
        key = (font_name, font_style, font_size)
        if key in self.font_data:
            return self.font_data[key]

        if font_name not in self.supported_fonts:
            raise ValueError("Font {} not supported".format(font_name))
        if font_style not in self.supported_styles:
            raise ValueError("Font style {} not supported".format(font_style))
        font_path = os.path.join(self.font_folder, font_name, "{}-{}.ttf".format(font_name, font_style))
        face = ft.Face(font_path)
        face.set_pixel_sizes(0, font_size)
        # Store fonts in dictionary mapping character code to Character object
        font_chars = {}
        # Load in all characters within the valid ASCII range (not SPACE or DEL)
        char_codes = [c[0] for c in face.get_chars() if c[0] > 32 and c[0] < 127]
        # Loop through characters and generate bitmaps
        for code in char_codes:
            face.load_char(code, flags=ft.FT_LOAD_RENDER)
            g = face.glyph
            bmap = g.bitmap
            # Convert list buffer into int numpy array so we can access raw data easily in C++ code
            buffer_data = np.ascontiguousarray(bmap.buffer, dtype=np.int32)
            tex_id = self.renderer.r.loadCharTexture(bmap.rows, bmap.width, buffer_data)
            self.tex_ids.append(tex_id)
            next_c = Character(tex_id, [bmap.width, bmap.rows], [g.bitmap_left, g.bitmap_top], g.advance.x, bmap.buffer)
            font_chars[code] = next_c

        # Store font character dictionary in main font_data dictionary, under current font
        self.font_data[(font_name, font_style, font_size)] = font_chars
        return font_chars


class Text(object):
    """
    Text objects store information required to render a block of text.
    """

    def __init__(
        self,
        text_data="PLACEHOLDER: PLEASE REPLACE!",
        font_name="OpenSans",
        font_style="Regular",
        font_size=48,
        color=[0, 0, 0],
        pos=[0, 0],
        scale=1.0,
        tbox_height=500,
        tbox_width=500,
        render_to_tex=False,
        background_color=None,
        text_manager=None,
    ):
        """
        :param text_data: starting text to display (can be changed at a later time by set_text)
        :param font_name: name of font to render - same as font folder in iGibson assets
        :param font_size: size of font to render
        :param font_style: style of font - one of [regular, italic, bold]
        :param color: [r, g, b] color
        :param pos: [x, y] position of text box's top-left corner on screen, in pixels
        :param scale: scale factor for resizing text
        :param tbox_height: height of text box
        :param tbox_width: width of text box
        :param render_to_tex: whether text should be rendered to an OpenGL texture or the screen (the default)
        :param background_color: color of the background in form [r, g, b, a] - background will only appear if this is not None
        :param text_manager: TextManager object that handles raw character data for fonts
        """
        if not text_manager:
            raise ValueError("Each Text object requires a TextManager reference")
        self.font_name = font_name
        self.font_style = font_style
        # Padding that appears at start and end of text
        self.text_pad = "-----"
        # Note: font size is in pixels
        self.font_size = font_size
        self.render_to_tex = render_to_tex
        self.line_sep = 1.5 * self.font_size
        self.space_x = int(self.font_size / 2)
        # Text stores list of lines, which are each rendered
        self.pos = pos
        self.scale = scale
        self.color = color
        self.background_color = background_color
        # Background margin in pixels (in both x and y directions)
        self.background_margin = 15
        self.tbox_height = tbox_height
        self.tbox_width = tbox_width
        # Text manager stores data for characters in a font
        self.tm = text_manager
        # Load font and extract character data
        self.char_data = self.tm.load_font(self.font_name, self.font_style, self.font_size)
        self.VAO, self.VBO = self.tm.renderer.r.setupTextRender()
        # Text shows by default after it is first created
        self.show_text = True
        self.set_text(text_data)

    def set_text(self, input_text):
        """
        :param input_text: text to display - lines must be separated by the newline character
        """
        self.text = input_text.splitlines()
        # By default add '-----' to the start/end of the text to indicate the top/bottom
        self.text.insert(0, self.text_pad)
        self.text.append(self.text_pad)
        self.gen_text_pos()

    def set_attribs(self, pos=None, scale=None, color=None):
        """
        Sets various text attributes.
        :param pos: [x, y] position of text box's top-left corner on screen, in pixels
        :param scale: scale factor for resizing text
        :param color: color of text in form [R, G, B] where R, G, B are in [0, 1]
        """
        if pos:
            self.pos = pos
        if scale:
            self.scale = scale
        if color:
            self.color = color

        # Don't need to regenerate text if color has been changed
        if pos or scale:
            self.gen_text_pos()

    def set_show_state(self, state):
        """
        Sets whether to hide/show text.
        :param state: bool indicating whether to show (True) or hide (False)
        """
        self.show_text = state

    def get_show_state(self):
        """
        Returns show state of Text.
        """
        return self.show_text

    def gen_text_pos(self):
        """
        Generates position for all characters in text. This is called every time
        some attribute of the text changes - either the text itself, or its pos, scale, etc.
        """
        # Use stack (deque) to support quick removal/addition of lines
        text_render_q = deque(self.text)
        # Store character render data as list of tuples (xpos, ypos, w, h, tex_id)
        self.char_render_data = []
        line_num = 1
        while text_render_q:
            line = text_render_q.popleft()
            next_x = self.pos[0] + self.background_margin
            next_y = self.pos[1] - line_num * self.line_sep
            for i in range(len(line)):
                # Convert character to ASCII
                c = ord(line[i])
                # Spaces are allowed to run into margins
                if c <= 32 or c >= 127:
                    next_x += self.space_x
                    continue

                c_data = self.char_data[c]
                xpos = next_x + c_data.bearing[0] * self.scale
                ypos = next_y - (c_data.size[1] - c_data.bearing[1]) * self.scale
                w = c_data.size[0] * self.scale
                h = c_data.size[1] * self.scale
                is_over_margin = xpos + w > self.pos[0] + self.tbox_width - self.background_margin

                if i == 0:
                    self.char_render_data.append((xpos, ypos, w, h, c_data.tex_id))
                else:
                    if is_over_margin:
                        remaining_line = "-" + line[i:]
                        text_render_q.appendleft(remaining_line)
                        break
                    else:
                        self.char_render_data.append((xpos, ypos, w, h, c_data.tex_id))

                # Advance x position to next glyph - advance is stored in units of 1/64 pixels, so we need to divide by 64
                next_x += (c_data.advance / 64.0) * self.scale

            line_num += 1

    def scroll_text(self, up=True):
        """
        Scrolls text within the text box. The "up" direction
        is one where the user scrolls to see higher up text,
        which results in the text box moving down.
        :param up: True to scroll up, False to scroll down.
        """
        if up:
            # Check if first line is on screen
            highest_char = sorted(self.char_render_data, key=lambda x: x[1] + x[3])[::-1][0]
            highest_y_pos = highest_char[1] + highest_char[3]
            if highest_y_pos > self.pos[1] - self.background_margin:
                # Only scroll up if highest line is not displayed
                self.char_render_data = [(t[0], t[1] - self.line_sep, t[2], t[3], t[4]) for t in self.char_render_data]
        else:
            # Check if last line is on screen
            lowest_y_pos = sorted(self.char_render_data, key=lambda x: x[1])[0][1]
            if lowest_y_pos < self.pos[1] - self.tbox_height + self.background_margin:
                # Only scroll down if lowest line is not displayed
                self.char_render_data = [(t[0], t[1] + self.line_sep, t[2], t[3], t[4]) for t in self.char_render_data]

    def render(self):
        """
        Render the current text object
        """
        # Text must be registered in order to render
        if not self.text:
            return
        if self.tm.renderer is None:
            return
        if not self.show_text:
            return

        # Pass in -1 if we want to render to the screen
        self.tm.renderer.r.preRenderText(
            self.tm.renderer.textShaderProgram,
            self.tm.FBO if self.render_to_tex else -1,
            self.VAO,
            self.color[0],
            self.color[1],
            self.color[2],
        )

        # Optionally render background first so alpha blending works correctly
        if self.background_color:
            bottom_left_x = self.pos[0]
            bottom_left_y = self.pos[1] - self.tbox_height
            b_w = self.tbox_width
            b_h = self.tbox_height

            # Unpack color data
            b_r, b_g, b_b, b_a = self.background_color
            # Render background
            self.tm.renderer.r.renderBackgroundQuad(
                bottom_left_x, bottom_left_y, b_w, b_h, self.VBO, self.tm.renderer.textShaderProgram, b_a, b_r, b_g, b_b
            )

        # Finally render characters - but only those within the text box
        for r_data in self.char_render_data:
            xpos, ypos, w, h, tex_id = r_data
            if (
                ypos + h <= self.pos[1] - self.background_margin
                and ypos >= self.pos[1] - self.tbox_height + self.background_margin
            ):
                self.tm.renderer.r.renderChar(xpos, ypos, w, h, tex_id, self.VBO)

        # Perform render clean-up
        self.tm.renderer.r.postRenderText()
