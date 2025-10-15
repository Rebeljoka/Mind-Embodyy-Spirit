/**
 * Tailwind CSS v4 configuration for the theme app.
 *
 * This file registers the DaisyUI plugin and sets `content` globs so Tailwind
 * and the editor's intellisense can find template and source files.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: [
  "./templates/**/*.html",
  "./**/*.{js,py,html}",
],
  theme: {
    extend: {},
  },
  plugins: [require('daisyui'), require('@tailwindcss/typography'), require('@tailwindcss/forms')],
  daisyui: {
    themes: ["caramellatte", "luxury"],
  },
};