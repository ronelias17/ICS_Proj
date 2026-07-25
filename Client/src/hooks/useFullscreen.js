import { useCallback, useEffect, useState } from 'react';

function browserSupportsFullscreen() {
    return Boolean(document.fullscreenEnabled && document.documentElement.requestFullscreen);
}

export function useFullscreen() {
    const [isFullscreen, setIsFullscreen] = useState(() => Boolean(document.fullscreenElement));
    const isSupported = browserSupportsFullscreen();

    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(Boolean(document.fullscreenElement));
        };

        document.addEventListener('fullscreenchange', handleFullscreenChange);

        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    const toggleFullscreen = useCallback(async () => {
        if (!browserSupportsFullscreen()) {
            return false;
        }

        try {
            if (document.fullscreenElement) {
                await document.exitFullscreen();
            } else {
                await document.documentElement.requestFullscreen();
            }
            return true;
        } catch (error) {
            console.warn('Fullscreen request failed:', error);
            return false;
        }
    }, []);

    return {
        isFullscreen,
        isSupported,
        toggleFullscreen,
    };
}