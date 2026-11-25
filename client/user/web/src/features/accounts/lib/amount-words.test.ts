import { describe, expect, it } from "vitest";
import { amountInWords, integerToIndianWords } from "./amount-words";

describe("amountInWords", () => {
  it("spells Indian groupings", () => {
    expect(integerToIndianWords(0n)).toBe("Zero");
    expect(integerToIndianWords(7n)).toBe("Seven");
    expect(integerToIndianWords(19n)).toBe("Nineteen");
    expect(integerToIndianWords(40n)).toBe("Forty");
    expect(integerToIndianWords(101n)).toBe("One Hundred One");
    expect(integerToIndianWords(1000n)).toBe("One Thousand");
    expect(integerToIndianWords(100000n)).toBe("One Lakh");
    expect(integerToIndianWords(1234567n)).toBe("Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven");
    expect(integerToIndianWords(10000000n)).toBe("One Crore");
    expect(integerToIndianWords(1500000000n)).toBe("One Hundred Fifty Crore");
    expect(integerToIndianWords(123456789012n)).toBe(
      "Twelve Thousand Three Hundred Forty Five Crore Sixty Seven Lakh Eighty Nine Thousand Twelve",
    );
  });
  it("matches the invoice design", () => {
    expect(amountInWords("291318.00")).toBe("INR Two Lakh Ninety One Thousand Three Hundred Eighteen Only");
    expect(amountInWords("86400")).toBe("INR Eighty Six Thousand Four Hundred Only");
  });
  it("handles paise, zero and negatives", () => {
    expect(amountInWords("1250.40")).toBe("INR One Thousand Two Hundred Fifty and Forty Paise Only");
    expect(amountInWords("0.05")).toBe("INR Five Paise Only");
    expect(amountInWords("0")).toBe("INR Zero Only");
    expect(amountInWords("-12")).toBe("INR Minus Twelve Only");
    expect(amountInWords("99.999")).toBe("INR One Hundred Only");
    expect(amountInWords("5", { prefix: "Rupees" })).toBe("Rupees Five Only");
  });
});
