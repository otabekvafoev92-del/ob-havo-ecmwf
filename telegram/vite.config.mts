import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));
export default defineConfig({
 root:`${root}/telegram`,
 publicDir:`${root}/public`,
 resolve:{alias:{'@':root}},
 plugins:[react()],
 build:{outDir:`${root}/telegram-dist`,emptyOutDir:true},
 css:{postcss:`${root}`},
});
