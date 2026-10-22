/* eslint-disable @typescript-eslint/no-require-imports -- jest.mock factories must use require */
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// Icon fonts load through the native asset registry, which Jest doesn't have.
jest.mock("@expo/vector-icons/Ionicons", () => {
  const { Text } = jest.requireActual<typeof import("react-native")>("react-native");
  const Ionicons = ({ name }: { name: string }) => <Text>{`icon:${name}`}</Text>;
  return { __esModule: true, default: Ionicons };
});
