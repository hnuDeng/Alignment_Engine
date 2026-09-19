import { ActionType } from './agentSlice';

export class SocketMiddlewareException extends Error {
    constructor(message: string) {
        super(`SocketMiddlewareException: ${message}`);
        this.name = 'SocketMiddlewareException';
    }
}

export class DataNormalizationException extends SocketMiddlewareException {
    constructor(message: string) {
        super(`DataNormalization: ${message}`);
        this.name = 'DataNormalizationException';
    }
}

export class ConnectionTimeoutException extends SocketMiddlewareException {
    constructor(message: string) {
        super(`ConnectionTimeout: ${message}`);
        this.name = 'ConnectionTimeoutException';
    }
}

// Complex JSON flattening algorithm for Data Normalization
function flattenJSON(obj: any, prefix = ''): any {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj !== 'object') return { [prefix.slice(0, -1)]: obj };

    return Object.keys(obj).reduce((acc: any, k: string) => {
        const pre = prefix.length ? prefix + '_' : '';
        if (typeof obj[k] === 'object' && obj[k] !== null && !Array.isArray(obj[k])) {
            Object.assign(acc, flattenJSON(obj[k], pre + k + '_'));
        } else {
            acc[pre + k] = obj[k];
        }
        return acc;
    }, {});
}

export const socketMiddleware = (url: string) => {
    let socket: WebSocket | null = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 10;
    let heartbeatInterval: any = null;

    return (store: any) => (next: any) => (action: ActionType) => {
        const connect = () => {
            if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
                return;
            }

            store.dispatch({ type: 'SOCKET_CONNECTING' });
            
            try {
                socket = new WebSocket(url);
            } catch (e) {
                handleDisconnect();
                return;
            }

            socket.onopen = () => {
                reconnectAttempts = 0;
                store.dispatch({ type: 'SOCKET_CONNECTED' });
                
                // Start heartbeat
                heartbeatInterval = setInterval(() => {
                    if (socket && socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({ type: 'PING' }));
                    }
                }, 30000);
            };

            socket.onmessage = (event) => {
                try {
                    const rawData = JSON.parse(event.data);
                    
                    // Data Normalization (Flattening)
                    const normalizedData = flattenJSON(rawData);
                    
                    if (!normalizedData.type) {
                        throw new DataNormalizationException("Message missing 'type' field after normalization");
                    }

                    store.dispatch(normalizedData as ActionType);
                } catch (err: any) {
                    console.error("Socket message processing failed:", err);
                    store.dispatch({ type: 'ERROR', payload: { message: err.message } });
                }
            };

            socket.onclose = () => {
                handleDisconnect();
            };

            socket.onerror = (_err) => {
                store.dispatch({ type: 'SOCKET_ERROR', payload: { code: -1 } });
            };
        };

        const handleDisconnect = () => {
            store.dispatch({ type: 'SOCKET_DISCONNECTED' });
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                // Exponential backoff reconnect
                const backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                reconnectAttempts++;
                console.log(`Socket disconnected. Reconnecting in ${backoffDelay}ms (Attempt ${reconnectAttempts})`);
                setTimeout(connect, backoffDelay);
            } else {
                throw new ConnectionTimeoutException("Max reconnect attempts reached. Network is permanently unreachable.");
            }
        };

        // Initialize connection on first INIT_PIPELINE action
        if (action.type === 'INIT_PIPELINE' && !socket) {
            connect();
        }

        // Pass action to reducers
        const result = next(action);

        // Forward certain actions to the server
        if (socket && socket.readyState === WebSocket.OPEN) {
            if (action.type.startsWith('EXTRACT_') || action.type.startsWith('ANALYZE_')) {
                socket.send(JSON.stringify(action));
            }
        }

        return result;
    };
};
