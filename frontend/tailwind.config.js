/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    DEFAULT: '#667EEA',
                    dark: '#5568D3',
                },
                success: '#48BB78',
                error: '#F56565',
                dark: {
                    bg: '#0A0E27',
                    card: '#222844',
                    border: '#2D3748',
                    appbar: '#1A1F3A',
                }
            },
        },
    },
    plugins: [],
}
