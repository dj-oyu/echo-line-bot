module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/test'],
  testMatch: ['**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest'
  },
  
  // Coverage configuration
  collectCoverage: true,
  collectCoverageFrom: [
    '<rootDir>/lib/**/*.ts',
    '!<rootDir>/lib/**/*.d.ts',
    '!<rootDir>/node_modules/**'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'html', 'lcov'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  
  // Snapshot configuration
  updateSnapshot: false,
  
  // Test organization
  testTimeout: 30000,
  verbose: true,
  
  // Module resolution
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // Test setup
  // setupFilesAfterEnv: ['<rootDir>/test/setup.ts'],
  
  // Ignore patterns
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/cdk.out/',
    '<rootDir>/lib/'
  ]
};
