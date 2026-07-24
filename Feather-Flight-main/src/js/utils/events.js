export function on(target, eventName, handler, options) {
  target.addEventListener(eventName, handler, options);

  return function off() {
    target.removeEventListener(eventName, handler, options);
  };
}

export function createEventBus() {
  const listeners = new Map();

  return {
    on(eventName, handler) {
      if (!listeners.has(eventName)) {
        listeners.set(eventName, new Set());
      }

      listeners.get(eventName).add(handler);

      return () => {
        listeners.get(eventName)?.delete(handler);
      };
    },

    emit(eventName, payload) {
      listeners.get(eventName)?.forEach((handler) => {
        handler(payload);
      });
    },

    clear(eventName) {
      if (eventName) {
        listeners.delete(eventName);
      } else {
        listeners.clear();
      }
    }
  };
}
