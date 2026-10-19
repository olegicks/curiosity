/* eslint-disable @typescript-eslint/no-require-imports -- jest.mock factories must use require */
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
