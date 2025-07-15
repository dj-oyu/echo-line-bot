/**
 * Test Setup Configuration
 * 
 * This file configures the test environment following t_wada's principles:
 * - Consistent test environment setup
 * - Proper test isolation
 * - Comprehensive test configuration
 * - Performance optimization
 */

import { jest } from '@jest/globals';

// Configure Jest timeout for CDK tests
jest.setTimeout(30000);

// Mock environment variables for consistent testing
const mockEnvVars = {
  CDK_DEFAULT_ACCOUNT: '123456789012',
  CDK_DEFAULT_REGION: 'us-east-1',
  AWS_REGION: 'us-east-1',
  NODE_ENV: 'test'
};

// Set up environment variables before tests
beforeAll(() => {
  Object.entries(mockEnvVars).forEach(([key, value]) => {
    process.env[key] = value;
  });
});

// Clean up after tests
afterAll(() => {
  Object.keys(mockEnvVars).forEach(key => {
    delete process.env[key];
  });
});

// Configure console output for tests
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

beforeEach(() => {
  // Suppress CDK warnings during tests unless explicitly needed
  console.warn = (message: string, ...args: any[]) => {
    if (message.includes('deprecated') || message.includes('warning')) {
      return;
    }
    originalConsoleWarn(message, ...args);
  };

  console.error = (message: string, ...args: any[]) => {
    if (message.includes('deprecated') || message.includes('warning')) {
      return;
    }
    originalConsoleError(message, ...args);
  };
});

afterEach(() => {
  console.warn = originalConsoleWarn;
  console.error = originalConsoleError;
});

// Custom matchers for CDK testing
expect.extend({
  toHaveResourceWithProperties(received: any, resourceType: string, properties: any) {
    try {
      received.hasResourceProperties(resourceType, properties);
      return {
        message: () => `Expected template to have resource ${resourceType} with properties`,
        pass: true
      };
    } catch (error) {
      return {
        message: () => `Expected template to have resource ${resourceType} with properties: ${error}`,
        pass: false
      };
    }
  },

  toHaveResourceCount(received: any, resourceType: string, count: number) {
    try {
      received.resourceCountIs(resourceType, count);
      return {
        message: () => `Expected template to have ${count} resources of type ${resourceType}`,
        pass: true
      };
    } catch (error) {
      return {
        message: () => `Expected template to have ${count} resources of type ${resourceType}: ${error}`,
        pass: false
      };
    }
  }
});

// Type declarations for custom matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toHaveResourceWithProperties(resourceType: string, properties: any): R;
      toHaveResourceCount(resourceType: string, count: number): R;
    }
  }
}

// Global test utilities
global.testUtils = {
  mockAwsAccount: mockEnvVars.CDK_DEFAULT_ACCOUNT,
  mockAwsRegion: mockEnvVars.CDK_DEFAULT_REGION,
  
  suppressConsoleOutput: () => {
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
  },
  
  restoreConsoleOutput: () => {
    jest.restoreAllMocks();
  }
};

// Configure test performance
beforeAll(() => {
  // Increase heap size for CDK tests if needed
  if (process.env.NODE_OPTIONS?.includes('--max-old-space-size') === false) {
    process.env.NODE_OPTIONS = `${process.env.NODE_OPTIONS || ''} --max-old-space-size=4096`;
  }
});

export {};