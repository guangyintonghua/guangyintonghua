STEALTH_JS = """
// 清除 webdriver 标志
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 清除 playwright 全局变量
(function() {
    const keys = ['__playwright', '__pw_manual', '__pwInitScripts', '__PW_inspect__',
                  '__playwright__clock__', '__pwClockSerial'];
    keys.forEach(k => { try { delete window[k]; } catch(e) {} });
    // 拦截后续注入
    const orig = Object.defineProperty.bind(Object);
    Object.defineProperty = function(obj, prop, desc) {
        if (obj === window && typeof prop === 'string' && prop.startsWith('__pw')) return obj;
        return orig(obj, prop, desc);
    };
})();

// 伪造真实插件列表
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const fakePlugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        const arr = Object.assign([...fakePlugins], {
            length: fakePlugins.length,
            item: i => fakePlugins[i] || null,
            namedItem: n => fakePlugins.find(p => p.name === n) || null,
            refresh: () => {}
        });
        return arr;
    }
});

// 伪造语言
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });

// Canvas 噪声注入
(function() {
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
        const data = origGetImageData.call(this, x, y, w, h);
        const noise = window.__canvasNoiseSeed || 1;
        for (let i = 0; i < data.data.length; i += 4) {
            data.data[i]   = Math.max(0, Math.min(255, data.data[i]   + (((i * noise) % 3) - 1)));
            data.data[i+1] = Math.max(0, Math.min(255, data.data[i+1] + (((i * noise * 7) % 3) - 1)));
            data.data[i+2] = Math.max(0, Math.min(255, data.data[i+2] + (((i * noise * 13) % 3) - 1)));
        }
        return data;
    };
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const img = ctx.getImageData(0, 0, this.width, this.height);
                const seed = window.__canvasNoiseSeed || 1;
                img.data[0] = Math.max(0, Math.min(255, img.data[0] + (seed % 3) - 1));
                ctx.putImageData(img, 0, 0);
            } catch(e) {}
        }
        return origToDataURL.call(this, type, quality);
    };
})();

// WebGL 噪声注入
(function() {
    const origReadPixels = WebGLRenderingContext.prototype.readPixels;
    WebGLRenderingContext.prototype.readPixels = function(...args) {
        origReadPixels.apply(this, args);
        const pixels = args[6];
        if (pixels instanceof Uint8Array && pixels.length > 4) {
            const seed = window.__canvasNoiseSeed || 1;
            pixels[0] = pixels[0] ^ (seed & 1);
            pixels[3] = pixels[3] ^ ((seed >> 1) & 1);
        }
    };
    const origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return origGetParam.call(this, param);
    };
})();

// 修复 chrome 对象
if (!window.chrome) {
    window.chrome = {
        runtime: {
            id: undefined,
            connect: function() {},
            sendMessage: function() {}
        },
        loadTimes: function() { return { requestTime: Date.now()/1000, startLoadTime: Date.now()/1000, commitLoadTime: Date.now()/1000, finishDocumentLoadTime: Date.now()/1000, finishLoadTime: Date.now()/1000, firstPaintTime: Date.now()/1000, firstPaintAfterLoadTime: 0, navigationType: 'Other', wasFetchedViaSpdy: false, wasNpnNegotiated: false, npnNegotiatedProtocol: 'unknown', wasAlternateProtocolAvailable: false, connectionInfo: 'http/1.1' }; },
        csi: function() { return { startE: Date.now(), onloadT: Date.now(), pageT: Date.now(), tran: 15 }; },
        app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } }
    };
}

// Notification 权限
try {
    const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
    window.navigator.permissions.query = (params) => {
        if (params.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return origQuery(params);
    };
} catch(e) {}

// 修复 toString 防检测
const origFunc = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === Function.prototype.toString) return 'function toString() { [native code] }';
    const s = origFunc.call(this);
    if (s.includes('getImageData') || s.includes('readPixels')) return 'function () { [native code] }';
    return s;
};
"""
