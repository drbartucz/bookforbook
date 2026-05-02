import '@testing-library/jest-dom/vitest';

globalThis.ResizeObserver = class ResizeObserver {
	observe() {}
	unobserve() {}
	disconnect() {}
};

function createLocalStorageMock() {
	let storage = {};

	return {
		getItem: (key) => (key in storage ? storage[key] : null),
		setItem: (key, value) => {
			storage[key] = String(value);
		},
		removeItem: (key) => {
			delete storage[key];
		},
		clear: () => {
			storage = {};
		},
	};
}

Object.defineProperty(globalThis, 'localStorage', {
	value: createLocalStorageMock(),
	writable: true,
});
